// Nanobot Web Frontend Application
// Main application logic for the chat interface

// Global variables
let currentRequestId = null;
let authToken = localStorage.getItem('authToken') || null;
let currentMessage = '';
let isTyping = false;
let selectedFiles = [];

// API Configuration
const API_BASE = '/api';

// Initialize the application
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

function initializeApp() {
    setupEventListeners();
    checkAuthentication();
    setupFileUpload();
}

// Authentication functions
function checkAuthentication() {
    if (!authToken) {
        showAuthModal();
        return;
    }

    // Validate token by getting user info
    fetch(`${API_BASE}/user`, {
        headers: {
            'Authorization': `Bearer ${authToken}`
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Invalid token');
        }
    })
    .then(data => {
        updateUserInfo(data);
    })
    .catch(error => {
        localStorage.removeItem('authToken');
        authToken = null;
        showAuthModal();
    });
}

function showAuthModal() {
    const authModal = document.getElementById('authModal');
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');

    authModal.style.display = 'block';

    loginForm.addEventListener('submit', handleLogin);
    registerForm.addEventListener('submit', handleRegister);

    // Tab switching
    document.getElementById('loginTab').addEventListener('click', () => {
        loginForm.style.display = 'block';
        registerForm.style.display = 'none';
        document.getElementById('loginTab').classList.add('active');
        document.getElementById('registerTab').classList.remove('active');
    });

    document.getElementById('registerTab').addEventListener('click', () => {
        loginForm.style.display = 'none';
        registerForm.style.display = 'block';
        document.getElementById('registerTab').classList.add('active');
        document.getElementById('loginTab').classList.remove('active');
    });
}

function handleLogin(event) {
    event.preventDefault();

    const username = document.getElementById('loginUsername').value;
    const password = document.getElementById('loginPassword').value;

    fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.access_token) {
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            closeAuthModal();
            checkAuthentication();
        } else {
            showError('Login failed: ' + (data.detail || 'Invalid credentials'));
        }
    })
    .catch(error => {
        showError('Login failed: ' + error.message);
    });
}

function handleRegister(event) {
    event.preventDefault();

    const username = document.getElementById('registerUsername').value;
    const email = document.getElementById('registerEmail').value;
    const password = document.getElementById('registerPassword').value;

    fetch(`${API_BASE}/auth/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ username, email, password })
    })
    .then(response => response.json())
    .then(data => {
        if (data.access_token) {
            authToken = data.access_token;
            localStorage.setItem('authToken', authToken);
            closeAuthModal();
            checkAuthentication();
        } else {
            showError('Registration failed: ' + (data.detail || 'Invalid data'));
        }
    })
    .catch(error => {
        showError('Registration failed: ' + error.message);
    });
}

function closeAuthModal() {
    document.getElementById('authModal').style.display = 'none';
    document.getElementById('loginForm').reset();
    document.getElementById('registerForm').reset();
}

// Event listener setup
function setupEventListeners() {
    const chatForm = document.getElementById('chatForm');
    const messageInput = document.getElementById('messageInput');
    const clearButton = document.getElementById('clearButton');
    const logoutButton = document.getElementById('logoutButton');

    chatForm.addEventListener('submit', handleChatSubmit);
    clearButton.addEventListener('click', clearChat);
    logoutButton.addEventListener('click', handleLogout);

    // File input handling
    const fileInput = document.getElementById('fileInput');
    fileInput.addEventListener('change', handleFileSelect);

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyPress);
}

// Chat functionality
function handleChatSubmit(event) {
    event.preventDefault();

    const message = document.getElementById('messageInput').value.trim();
    if (!message || isTyping) return;

    currentMessage = message;
    addMessageToChat(message, 'user');
    document.getElementById('messageInput').value = '';

    isTyping = true;
    showTypingIndicator();

    // Create new request ID
    currentRequestId = generateRequestId();

    // Send message to API
    sendMessageToAPI(message);
}

function sendMessageToAPI(message) {
    const requestData = {
        message: message,
        files: selectedFiles,
        request_id: currentRequestId
    };

    fetch(`${API_BASE}/chat/send`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${authToken}`
        },
        body: JSON.stringify(requestData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.request_id) {
            currentRequestId = data.request_id;
            streamResponse();
        } else {
            throw new Error('Failed to send message');
        }
    })
    .catch(error => {
        hideTypingIndicator();
        showError('Error sending message: ' + error.message);
        isTyping = false;
    });
}

function streamResponse() {
    const eventSource = new EventSource(
        `${API_BASE}/chat/stream?request_id=${currentRequestId}`,
        { headers: { 'Authorization': `Bearer ${authToken}` } }
    );

    eventSource.onopen = function() {
        console.log('SSE connection opened');
    };

    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);

        if (data.type === 'response') {
            hideTypingIndicator();
            addMessageToChat(data.content, 'assistant');
            isTyping = false;
            eventSource.close();
        } else if (data.type === 'typing') {
            updateTypingIndicator(data.content);
        } else if (data.type === 'error') {
            hideTypingIndicator();
            showError(data.message);
            isTyping = false;
            eventSource.close();
        }
    };

    eventSource.onerror = function() {
        hideTypingIndicator();
        showError('Connection error');
        isTyping = false;
        eventSource.close();
    };
}

// UI Functions
function addMessageToChat(content, sender) {
    const chatMessages = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${sender}`;

    const timestamp = new Date().toLocaleTimeString();
    messageDiv.innerHTML = `
        <div class="message-header">
            <span class="sender">${sender}</span>
            <span class="timestamp">${timestamp}</span>
        </div>
        <div class="message-content">${formatMessage(content)}</div>
    `;

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatMessage(content) {
    // Simple markdown-like formatting
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code>$1</code>')
        .replace(/\n/g, '<br>');
}

function showTypingIndicator() {
    const chatMessages = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant typing';
    typingDiv.id = 'typingIndicator';

    typingDiv.innerHTML = `
        <div class="message-header">
            <span class="sender">assistant</span>
            <span class="timestamp">${new Date().toLocaleTimeString()}</span>
        </div>
        <div class="typing-content">
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
            <span class="typing-dot"></span>
        </div>
    `;

    chatMessages.appendChild(typingDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function updateTypingIndicator(content) {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.querySelector('.typing-content').innerHTML = formatMessage(content);
    }
}

function hideTypingIndicator() {
    const typingIndicator = document.getElementById('typingIndicator');
    if (typingIndicator) {
        typingIndicator.remove();
    }
}

function clearChat() {
    const chatMessages = document.getElementById('chatMessages');
    chatMessages.innerHTML = '';
}

// File handling
function setupFileUpload() {
    const dropZone = document.getElementById('dropZone');

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');

        const files = Array.from(e.dataTransfer.files);
        handleFiles(files);
    });
}

function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    handleFiles(files);
}

function handleFiles(files) {
    selectedFiles = selectedFiles.concat(files);
    updateFileList();
}

function updateFileList() {
    const fileList = document.getElementById('fileList');
    fileList.innerHTML = '';

    selectedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'file-item';
        fileItem.innerHTML = `
            <span>${file.name} (${formatFileSize(file.size)})</span>
            <button class="remove-file" onclick="removeFile(${index})">&times;</button>
        `;
        fileList.appendChild(fileItem);
    });
}

function removeFile(index) {
    selectedFiles.splice(index, 1);
    updateFileList();
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// Utility functions
function generateRequestId() {
    return 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;

    document.body.appendChild(errorDiv);

    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

function updateUserInfo(user) {
    const userInfo = document.getElementById('userInfo');
    userInfo.innerHTML = `
        <span>Welcome, ${user.username}</span>
        <button id="logoutButton" onclick="handleLogout()">Logout</button>
    `;
}

function handleLogout() {
    localStorage.removeItem('authToken');
    authToken = null;
    location.reload();
}

function handleKeyPress(event) {
    // Ctrl/Cmd + Enter to send message
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
        const messageInput = document.getElementById('messageInput');
        if (messageInput.value.trim()) {
            handleChatSubmit(new Event('submit'));
        }
    }

    // Escape to clear input
    if (event.key === 'Escape') {
        document.getElementById('messageInput').value = '';
    }
}