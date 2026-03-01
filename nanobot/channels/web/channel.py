"""Web channel implementation."""

import asyncio
from typing import Any

from loguru import logger
from uvicorn import Server

from nanobot.bus.events import InboundMessage, OutboundMessage
from nanobot.bus.queue import MessageBus
from nanobot.channels.base import BaseChannel
from nanobot.channels.web.api import create_app, pending_requests
from nanobot.channels.web.database import WebDatabase


class WebChannel(BaseChannel):
    """Web channel using FastAPI + SSE."""

    name = "web"

    def __init__(self, config: Any, bus: MessageBus):
        super().__init__(config, bus)
        self._server: Server | None = None
        self._db: WebDatabase | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the web server."""
        logger.info("Starting web channel on {}:{}", self.config.host, self.config.port)

        # Initialize database
        self._db = await WebDatabase.create(self.config.db_path)

        # Create FastAPI app
        app = create_app(
            db=self._db,
            secret=self.config.jwt_secret,
            allow_from=self.config.allow_from,
            bus=self.bus,
            cors_origins=self.config.cors_origins,
        )

        # Store references for message handling
        app.state.bus = self.bus
        app.state.db = self._db
        app.state.pending_requests = pending_requests

        # Configure uvicorn
        import uvicorn
        config = uvicorn.Config(
            app,
            host=self.config.host,
            port=self.config.port,
            log_level="info",
        )
        self._server = Server(config)

        # Start server in background task
        self._task = asyncio.create_task(self._server.serve())
        self._running = True

        logger.info("Web channel started on http://{}:{}", self.config.host, self.config.port)

    async def stop(self) -> None:
        """Stop the web server."""
        if not self._running:
            return

        logger.info("Stopping web channel")

        if self._server:
            self._server.should_exit = True

        if self._task:
            await asyncio.sleep(0.5)
            if not self._task.done():
                self._task.cancel()

        if self._db:
            await self._db.close()

        self._running = False
        logger.info("Web channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        """Send message through web channel."""
        request_id = msg.metadata.get("request_id")

        if not request_id:
            logger.warning("Outbound message missing request_id: {}", msg.metadata)
            return

        # Check if this is a progress message
        is_progress = msg.metadata.get("_progress", False)
        is_tool_hint = msg.metadata.get("_tool_hint", False)
        tool_calls_json = msg.metadata.get("_tool_calls")
        tool_calls = None
        if tool_calls_json:
            import json
            try:
                tool_calls = json.loads(tool_calls_json)
            except (json.JSONDecodeError, TypeError):
                pass

        # Store response for SSE streaming
        if request_id in pending_requests:
            if is_progress:
                # Append progress message
                if "progress" not in pending_requests[request_id]:
                    pending_requests[request_id]["progress"] = []
                progress_item = {
                    "content": msg.content,
                    "is_tool_hint": is_tool_hint,
                }
                if tool_calls:
                    progress_item["tool_calls"] = tool_calls
                pending_requests[request_id]["progress"].append(progress_item)
            else:
                # Final response
                pending_requests[request_id]["response"] = msg.content
                pending_requests[request_id]["done"] = True
        else:
            logger.warning("Unknown request_id: {}", request_id)