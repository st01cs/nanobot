// API base URL
const API_BASE = window.location.origin + '/api';

// Auth state
let authToken = localStorage.getItem('authToken');
let currentUser = null;

// Current chat session
let currentSessionId = null;

// Initialize app
document.addEventListener('DOMContentLoaded', () => {
    const path = window.location.pathname;

    if (path === '/') {
        initLoginPage();
    } else if (path === '/chat') {
        initChatPage();
    }
});

// ========== Login Page ==========
function initLoginPage() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const showRegister = document.getElementById('show-register');
    const showLogin = document.getElementById('show-login');

    showRegister?.addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('login-form').style.display = 'none';
        document.getElementById('register-form').style.display = 'block';
    });

    showLogin?.addEventListener('click', (e) => {
        e.preventDefault();
        document.getElementById('register-form').style.display = 'none';
        document.getElementById('login-form').style.display = 'block';
    });

    loginForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('login-username').value;
        const password = document.getElementById('login-password').value;

        try {
            const response = await fetch(`${API_BASE}/auth/login`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                const data = await response.json();
                authToken = data.access_token;
                currentUser = data.user;
                localStorage.setItem('authToken', authToken);
                window.location.href = '/chat';
            } else {
                showError('Invalid username or password');
            }
        } catch (err) {
            showError('Failed to connect to server');
        }
    });

    registerForm?.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = document.getElementById('reg-username').value;
        const password = document.getElementById('reg-password').value;

        try {
            const response = await fetch(`${API_BASE}/auth/register`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            if (response.ok) {
                const data = await response.json();
                authToken = data.access_token;
                currentUser = data.user;
                localStorage.setItem('authToken', authToken);
                window.location.href = '/chat';
            } else {
                const data = await response.json();
                showError(data.detail || 'Registration failed');
            }
        } catch (err) {
            showError('Failed to connect to server');
        }
    });
}

function showError(message) {
    const errorDiv = document.getElementById('error-message');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.add('show');
        setTimeout(() => errorDiv.classList.remove('show'), 5000);
    }
}

// ========== Chat Page ==========
function initChatPage() {
    if (!authToken) {
        window.location.href = '/';
        return;
    }

    loadUserInfo();
    loadChatHistory();

    const chatForm = document.getElementById('chat-form');
    const logoutBtn = document.getElementById('logout-btn');

    chatForm?.addEventListener('submit', sendMessage);
    logoutBtn?.addEventListener('click', logout);
}

async function loadUserInfo() {
    try {
        const response = await fetch(`${API_BASE}/auth/me`, {
            headers: { 'Authorization': `Bearer ${authToken}` }
        });

        if (response.ok) {
            currentUser = await response.json();
            const usernameDisplay = document.getElementById('username-display');
            if (usernameDisplay) {
                usernameDisplay.textContent = currentUser.username;
            }
        } else {
            logout();
        }
    } catch (err) {
        console.error('Failed to load user:', err);
    }
}

async function loadChatHistory() {
    if (!currentSessionId) return;

    try {
        const response = await fetch(
            `${API_BASE}/chat/history?session_id=${currentSessionId}`,
            { headers: { 'Authorization': `Bearer ${authToken}` } }
        );

        if (response.ok) {
            const data = await response.json();
            const messagesDiv = document.getElementById('messages');
            if (messagesDiv) {
                messagesDiv.innerHTML = '';

                data.messages.forEach(msg => {
                    appendMessage(msg.role, msg.content, false);
                });

                scrollToBottom();
            }
        }
    } catch (err) {
        console.error('Failed to load history:', err);
    }
}

async function sendMessage(e) {
    e.preventDefault();

    const input = document.getElementById('message-input');
    if (!input) return;

    const content = input.value.trim();

    if (!content) return;

    input.value = '';
    appendMessage('user', content);
    showTypingIndicator();

    try {
        const response = await fetch(`${API_BASE}/chat/completions`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content,
                session_id: currentSessionId
            })
        });

        if (response.ok) {
            const data = await response.json();
            currentSessionId = data.session_id;

            // Stream response
            streamResponse(data.request_id);
        } else {
            hideTypingIndicator();
            appendMessage('assistant', 'Sorry, something went wrong.');
        }
    } catch (err) {
        hideTypingIndicator();
        appendMessage('assistant', 'Failed to connect to server.');
        console.error(err);
    }
}

async function streamResponse(requestId) {
    const eventSource = new EventSource(
        `${API_BASE}/chat/stream?request_id=${requestId}&token=${authToken}`
    );

    let assistantMessage = null;
    let progressContainer = null;
    let fullContent = '';

    // Create progress container
    progressContainer = appendProgressContainer();

    eventSource.addEventListener('progress', (e) => {
        const data = JSON.parse(e.data);
        appendProgressItem(progressContainer, data.content, data.is_tool_hint, data.tool_calls);
        scrollToBottom();
    });

    eventSource.addEventListener('message', (e) => {
        const data = JSON.parse(e.data);

        if (!assistantMessage) {
            hideTypingIndicator();
            assistantMessage = appendMessage('assistant', '');
        }

        // Accumulate content during streaming
        fullContent += data.content;

        // Update with plain text during streaming for better performance
        if (assistantMessage) {
            assistantMessage.textContent = fullContent;
            scrollToBottom();
        }
    });

    eventSource.addEventListener('done', () => {
        // Render markdown after streaming is complete
        if (assistantMessage && fullContent) {
            renderMarkdown(assistantMessage, fullContent);
        }
        eventSource.close();
    });

    eventSource.addEventListener('error', () => {
        // Render markdown even on error
        if (assistantMessage && fullContent) {
            renderMarkdown(assistantMessage, fullContent);
        }
        eventSource.close();
        if (!assistantMessage) {
            hideTypingIndicator();
        }
    });
}

function appendMessage(role, content, scroll = true) {
    const messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return;

    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    // Render markdown for assistant messages
    if (role === 'assistant') {
        renderMarkdown(contentDiv, content);
    } else {
        contentDiv.textContent = content;
    }

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);

    if (scroll) scrollToBottom();

    return contentDiv;
}

/**
 * Render markdown content safely with DOMPurify
 * @param {HTMLElement} element - Target element to render into
 * @param {string} content - Markdown content to render
 */
function renderMarkdown(element, content) {
    // Configure marked options
    marked.setOptions({
        breaks: true,      // Convert \n to <br>
        gfm: true,         // GitHub Flavored Markdown
        headerIds: false,  // Don't generate header IDs
        mangle: false      // Don't mangle email addresses
    });

    // Parse markdown and sanitize HTML
    const html = DOMPurify.sanitize(marked.parse(content));
    element.innerHTML = html;
}

function showTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.style.display = 'flex';
        scrollToBottom();
    }
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typing-indicator');
    if (typingIndicator) {
        typingIndicator.style.display = 'none';
    }
}

function scrollToBottom() {
    const messagesDiv = document.getElementById('messages');
    if (messagesDiv) {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }
}

function appendProgressContainer() {
    const messagesDiv = document.getElementById('messages');
    if (!messagesDiv) return null;

    const progressDiv = document.createElement('div');
    progressDiv.className = 'progress-container';

    const header = document.createElement('div');
    header.className = 'progress-header';
    header.textContent = '🔧 执行工具...';

    const list = document.createElement('div');
    list.className = 'progress-list';

    progressDiv.appendChild(header);
    progressDiv.appendChild(list);
    messagesDiv.appendChild(progressDiv);

    return progressDiv;
}

function appendProgressItem(container, content, isToolHint, toolCalls) {
    if (!container) return;

    const list = container.querySelector('.progress-list');
    if (!list) return;

    // If we have detailed tool_calls data, use it
    if (isToolHint && toolCalls && toolCalls.length > 0) {
        toolCalls.forEach(toolCall => {
            const item = document.createElement('div');
            item.className = 'progress-item';

            const inner = document.createElement('div');
            inner.style.display = 'flex';
            inner.style.alignItems = 'flex-start';
            inner.style.gap = '8px';

            const icon = document.createElement('span');
            icon.className = 'progress-icon';
            icon.textContent = '⚡';

            const text = document.createElement('span');
            text.className = 'progress-text';
            const argsStr = JSON.stringify(toolCall.arguments, null, 2);
            text.textContent = `执行工具: ${toolCall.name}(${argsStr})`;

            inner.appendChild(icon);
            inner.appendChild(text);
            item.appendChild(inner);
            list.appendChild(item);
        });
    } else if (isToolHint) {
        // Fallback: split by comma if we don't have detailed tool_calls
        const toolHints = splitToolCalls(content);
        toolHints.forEach(hint => {
            const item = document.createElement('div');
            item.className = 'progress-item';

            const inner = document.createElement('div');
            inner.style.display = 'flex';
            inner.style.alignItems = 'flex-start';
            inner.style.gap = '8px';

            const icon = document.createElement('span');
            icon.className = 'progress-icon';
            icon.textContent = '⚡';

            const text = document.createElement('span');
            text.className = 'progress-text';
            text.textContent = '执行工具: ' + hint;

            inner.appendChild(icon);
            inner.appendChild(text);
            item.appendChild(inner);
            list.appendChild(item);
        });
    } else {
        // Simple progress item without tool hint
        const item = document.createElement('div');
        item.className = 'progress-item';

        const inner = document.createElement('div');
        inner.style.display = 'flex';
        inner.style.alignItems = 'flex-start';
        inner.style.gap = '8px';

        const icon = document.createElement('span');
        icon.className = 'progress-icon';
        icon.textContent = '…';

        const text = document.createElement('span');
        text.className = 'progress-text';
        text.textContent = content;

        inner.appendChild(icon);
        inner.appendChild(text);
        item.appendChild(inner);
        list.appendChild(item);
    }
}

/**
 * Split tool calls by comma, but only at the top level (outside parentheses/braces)
 * This correctly handles tool calls with complex parameters like: {"pattern": "a, b"}
 */
function splitToolCalls(content) {
    const result = [];
    let current = '';
    let depth = 0;  // Track nesting depth of parentheses/braces
    let inString = false;
    let escapeNext = false;

    for (let i = 0; i < content.length; i++) {
        const char = content[i];

        if (escapeNext) {
            current += char;
            escapeNext = false;
            continue;
        }

        if (char === '\\') {
            current += char;
            escapeNext = true;
            continue;
        }

        if (char === '"' && !escapeNext) {
            inString = !inString;
            current += char;
            continue;
        }

        if (inString) {
            current += char;
            continue;
        }

        // Track nesting depth
        if (char === '(' || char === '{' || char === '[') {
            depth++;
            current += char;
        } else if (char === ')' || char === '}' || char === ']') {
            depth--;
            current += char;
        } else if (char === ',' && depth === 0) {
            // Found separator at top level
            if (current.trim()) {
                result.push(current.trim());
            }
            current = '';
            // Skip the space after comma
            if (content[i + 1] === ' ') {
                i++;
            }
        } else {
            current += char;
        }
    }

    // Add the last tool call
    if (current.trim()) {
        result.push(current.trim());
    }

    return result;
}

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUser = null;
    currentSessionId = null;
    window.location.href = '/';
}
