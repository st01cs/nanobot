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

    eventSource.addEventListener('message', (e) => {
        const data = JSON.parse(e.data);

        if (!assistantMessage) {
            hideTypingIndicator();
            assistantMessage = appendMessage('assistant', '');
        }

        if (assistantMessage) {
            assistantMessage.textContent += data.content;
            scrollToBottom();
        }
    });

    eventSource.addEventListener('done', () => {
        eventSource.close();
    });

    eventSource.addEventListener('error', () => {
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
    contentDiv.textContent = content;

    messageDiv.appendChild(contentDiv);
    messagesDiv.appendChild(messageDiv);

    if (scroll) scrollToBottom();

    return contentDiv;
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

function logout() {
    localStorage.removeItem('authToken');
    authToken = null;
    currentUser = null;
    currentSessionId = null;
    window.location.href = '/';
}
