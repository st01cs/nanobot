# Multi-User Support Design for nanobot

**Date:** 2026-03-01
**Author:** Design Discussion
**Status:** Design Phase

## Overview

This document outlines the architecture and design for adding multi-user support to nanobot, transforming it from a single-user personal AI assistant into a SaaS platform capable of serving 100+ users with complete data isolation and security.

## Requirements Summary

- **Use Case:** SaaS service
- **User Scale:** Pilot phase (<100 users)
- **Isolation Level:** Container-level isolation
- **Authentication:** Web-based JWT authentication

## Architecture

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                        Nginx 反向代理                         │
│                   (SSL终止, 负载均衡, 静态资源)                │
└───────────────────────┬─────────────────────────────────────┘
                        │
                ┌───────┴────────┐
                ▼                ▼
┌───────────────────────┐  ┌──────────────────────┐
│   Web Gateway         │  │   容器管理API        │
│   (FastAPI/Flask)     │  │   (容器生命周期)     │
│                       │  │                      │
│   • JWT认证          │  │   • 创建/删除容器    │
│   • 用户注册         │  │   • 启动/停止容器    │
│   • 会话路由         │  │   • 资源监控         │
│   • WebSocket代理    │  │   • 日志收集         │
└───────────┬───────────┘  └──────────┬──────────┘
            │                         │
            │      容器专用网络       │
            │  (user-containers-net)  │
            │                         │
    ┌───────┴────────┐        ┌───────┴────────┐
    ▼                ▼        ▼                ▼
┌────────┐      ┌────────┐ ┌────────┐    ┌────────┐
│用户A   │      │用户B   │ │用户C   │    │用户D   │
│容器    │      │容器    │ │容器    │    │容器    │
│        │      │        │ │        │    │        │
│nanobot │      │nanobot │ │nanobot │    │nanobot │
│gateway │      │gateway │ │gateway │    │gateway │
└────────┘      └────────┘ └────────┘    └────────┘
```

### Core Components

1. **Web Gateway (FastAPI)**: Handles authentication, user management, WebSocket routing
2. **Container Manager**: Manages Docker container lifecycle using docker-py
3. **User Containers**: Isolated nanobot gateway instances per user
4. **Data Storage**: SQLite for metadata, filesystem for user data

## User Authentication & Session Management

### Registration & Login Flow

**POST /api/auth/register**
```json
Request: {username, password, email}
Response: {user_id, jwt_token, container_port}
```

**JWT Token Structure**
```json
{
  "user_id": "user_abc123",
  "username": "user_x",
  "iat": 1234567890,
  "exp": 1234570490,
  "container_name": "nanobot-user_abc123"
}
```

### WebSocket Connection Routing

Web Gateway establishes WebSocket connection to user containers:
1. Verify JWT token
2. Retrieve container port from database
3. Establish connection to container on port 18790
4. Bidirectional message forwarding

## Container Lifecycle Management

### Container Specification

```python
docker.create_container(
    name=f"nanobot-{user_id}",
    image="nanobot:latest",
    ports={'18790/tcp': None},
    volumes={
        f'/data/users/{user_id}/config': {'bind': '/root/.nanobot', 'mode': 'ro'},
        f'/data/users/{user_id}/workspace': {'bind': '/root/.nanobot/workspace', 'mode': 'rw'}
    },
    mem_limit="512m",
    cpu_quota=100000,
    network="user-containers-net"
)
```

### Lifecycle States

```
[不存在] → 注册 → [创建中] → [运行中] → [停止] → [已销毁]
                ↓                      ↓
            创建失败              异常(自动重启)
                ↓                      ↓
            [失败] ←───────────────────┘
```

### Resource Policies

- **Container Pool**: Pre-create 5 idle containers
- **Idle Timeout**: Stop containers after 2 hours of inactivity
- **Resource Limits**: 512MB RAM, 0.1 CPU core per container
- **Retention**: Keep data for 7 days after container stops

## Data Storage & Isolation

### Directory Structure

```
/data/
├── users/
│   ├── user_abc123/
│   │   ├── config/
│   │   │   ├── config.json
│   │   │   ├── credentials.json (encrypted)
│   │   │   └── skills/
│   │   ├── workspace/
│   │   │   ├── memory/
│   │   │   ├── files/
│   │   │   └── HEARTBEAT.md
│   │   ├── sessions/
│   │   └── logs/
│   └── user_def456/
├── database/
│   ├── users.db
│   └── containers.db
└── shared/
    └── public_skills/
```

### Database Schema

**users.db**
```sql
CREATE TABLE users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    status TEXT DEFAULT 'active',
    quota_used INTEGER DEFAULT 0,
    container_name TEXT,
    container_port INTEGER,
    subscription_tier TEXT DEFAULT 'free'
);
```

### Security Measures

- **Filesystem isolation**: Separate directories per user
- **Network isolation**: Dedicated Docker network, containers cannot communicate directly
- **API key encryption**: Fernet encryption for stored credentials
- **Path traversal protection**: Validate all file paths
- **Quota enforcement**: Limit resource usage per subscription tier

## API Interface Design

### Authentication APIs

- `POST /api/auth/register` - User registration
- `POST /api/auth/login` - User login
- `POST /api/auth/refresh` - Refresh JWT token
- `POST /api/auth/logout` - Logout
- `DELETE /api/auth/account` - Delete account

### User Management APIs

- `GET /api/users/me` - Get user info
- `PUT /api/users/me/config` - Update configuration
- `GET /api/users/me/quota` - Get quota usage
- `GET /api/users/me/sessions` - List sessions

### Container APIs

- `POST /api/containers/start` - Start container
- `POST /api/containers/stop` - Stop container
- `POST /api/containers/restart` - Restart container
- `GET /api/containers/status` - Get container status
- `GET /api/containers/logs` - Get container logs

### WebSocket Endpoint

`WS /ws/{token}` - Real-time communication with user's nanobot instance

## Deployment

### Docker Compose Stack

```yaml
services:
  nginx:
    image: nginx:alpine
    ports: ["80:80", "443:443"]

  web-gateway:
    build: ./services/web-gateway
    volumes: ["/var/run/docker.sock:/var/run/docker.sock"]

  redis:
    image: redis:alpine

  monitor:
    build: ./services/monitor
```

### Monitoring & Logging

- **Log aggregation**: Centralized logging with rotation
- **Metrics**: CPU, memory, active containers, WebSocket connections
- **Health checks**: Container health monitoring every 30 seconds
- **Alerts**: Email notifications for critical failures

### Backup Strategy

Daily automated backups:
1. SQLite databases
2. User configuration directories
3. Container metadata
4. Upload to cloud storage (S3)
5. Retain for 30 days

## Cost Estimation (100 Users)

### Hardware Requirements

- **CPU**: 16 cores
- **Memory**: 32GB (with oversubscription)
- **Storage**: 500GB SSD

### Cloud Costs (Monthly)

- AWS EC2 (r6i.xlarge): $200-300
- Alibaba Cloud ECS: ¥1500-2000

### Optimization

- Use Spot instances to reduce costs
- Container oversubscription ratio 1:2
- Periodic cleanup of idle containers

## Security Considerations

1. **Container Escape Prevention**: Use user namespaces, AppArmor profiles
2. **Resource Limits**: Enforce memory/CPU quotas via cgroups
3. **API Security**: Rate limiting, input validation, SQL injection prevention
4. **Data Encryption**: Encrypt sensitive data at rest
5. **Network Security**: Internal Docker network, firewall rules

## Migration Path

The system is designed to evolve from pilot to production:

- **Phase 1 (Pilot)**: Docker Compose, manual operations
- **Phase 2 (Growth)**: Add Kubernetes for orchestration
- **Phase 3 (Scale)**: Microservices architecture, distributed databases

## Next Steps

1. Review and approve this design
2. Implement detailed development plan (see: `2026-03-01-multi-user-implementation.md`)
3. Set up development environment
4. Begin implementation following TDD principles
