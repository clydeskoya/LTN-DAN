// Initialize Socket.IO connection
const socket = io();

// DOM elements
const messageInput = document.getElementById('messageInput');
const sendButton = document.getElementById('sendButton');
const chatMessages = document.getElementById('chatMessages');
const loadHistoryButton = document.getElementById('loadHistory');
const clearHistoryButton = document.getElementById('clearHistory');
const themeToggleButton = document.getElementById('themeToggle');
const audioButton = document.getElementById('audioButton');

// Create recording popup
const recordingPopup = document.createElement('div');
recordingPopup.className = 'recording-popup';
recordingPopup.innerHTML = `
    <div class="recording-content">
        <div class="recording-status">
            <i class="fas fa-microphone"></i>
            <span>Recording...</span>
        </div>
        <div class="recording-wave"></div>
        <button id="stopRecordingButton" class="retro-button">
            <i class="fas fa-stop"></i> Stop Recording
        </button>
    </div>
`;
document.body.appendChild(recordingPopup);

// Create loading popup
const loadingPopup = document.createElement('div');
loadingPopup.className = 'loading-popup';
loadingPopup.innerHTML = `
    <div class="loading-content">
        <div class="loading-spinner"></div>
        <div class="loading-text">Processing your message...</div>
    </div>
`;
document.body.appendChild(loadingPopup);

// Placeholder phrases
const placeholderPhrases = [
    "Oh, you're back. Need my expertise again?",
    "Let me guess... you need something brilliant?",
    "Ready to make your music slightly less mediocre?",
    "Your personal audio genius awaits...",
    "Finally, someone who appreciates real talent",
    "Ah, the artist returns. How may I elevate your work?",
    "Warning: Exceptional ideas incoming",
    "I suppose we should create something extraordinary?",
    "Your favorite audio assistant is listening...",
    "Turn your OK track into something remarkable.",
    "Another masterpiece in the making, I presume?",
    "Bringing the genius you clearly need",
    "Let's see what we can salvage here...",
    "Your musical guardian angel is listening",
    "I'm here to make your good ideas great",
    "Prepared to be impressed by my suggestions?",
    "The bar is low, but I'll help you raise it",
    "Your tracks could use my touch. I'm listening...",
    "Enlighten me with your musical predicament",
    "Here to save your project, as usual"
];

// Set random placeholder on page load
function setRandomPlaceholder() {
    const randomIndex = Math.floor(Math.random() * placeholderPhrases.length);
    messageInput.placeholder = placeholderPhrases[randomIndex];
}

// Handle audio button click
async function handleAudioButtonClick() {
    try {
        // Add recording visual feedback
        audioButton.classList.add('recording');
        audioButton.innerHTML = '<i class="fas fa-stop"></i>';
        
        // Show recording popup
        recordingPopup.style.display = 'flex';
        
        // Send request to start recording
        const response = await fetch('/start_recording', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        
    } catch (error) {
        console.error('Error starting recording:', error);
        // Hide popup and show error
        recordingPopup.style.display = 'none';
        alert(`Error: ${error.message}`);
    } finally {
        // Reset button state
        audioButton.classList.remove('recording');
        audioButton.innerHTML = '<i class="fas fa-microphone"></i>';
    }
}

// Handle stopping recording
async function handleStopRecording() {
    // Hide recording popup immediately
    recordingPopup.style.display = 'none';
    
    // Reset audio button state immediately
    audioButton.classList.remove('recording');
    audioButton.innerHTML = '<i class="fas fa-microphone"></i>';
    
    // Show loading popup
    loadingPopup.style.display = 'flex';
    
    try {
        // Send request to stop recording
        const response = await fetch('/stop_recording', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.status === 'error') {
            throw new Error(data.message);
        }
        
        // Keep loading popup visible until we receive a message
        // The popup will be hidden when we receive the message via Socket.IO
        
    } catch (error) {
        console.error('Error stopping recording:', error);
        alert(`Error: ${error.message}`);
        // Hide loading popup on error
        loadingPopup.style.display = 'none';
    }
}

// Check recording status
async function checkRecordingStatus() {
    try {
        const response = await fetch('/check_recording_status', {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        console.log('Recording status:', data);
        return data;
    } catch (error) {
        console.error('Error checking recording status:', error);
        return { status: 'error', message: error.message };
    }
}

// Handle receiving messages
socket.on('receive_message', (data) => {
    console.log('Received message:', data); // Debug log
    
    // Hide loading popup when we receive a message
    loadingPopup.style.display = 'none';
    
    // Check if this is a streaming message (no timestamp) or a complete message
    if (!data.timestamp) {
        // Streaming message - update the current message
        if (currentMessageDiv) {
            currentMessageDiv.textContent = data.content;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } else {
            // Create new message div if it doesn't exist
            currentMessageDiv = document.createElement('div');
            currentMessageDiv.className = 'message assistant';
            chatMessages.appendChild(currentMessageDiv);
            currentMessageDiv.textContent = data.content;
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    } else {
        // Complete message - create new message div
        addMessageToChat(data.role, data.content);
        // Reset currentMessageDiv for next streaming message
        currentMessageDiv = null;
    }
});

// Handle history loading
socket.on('history_loaded', (data) => {
    console.log('History loaded:', data); // Debug log
    // Clear current messages
    chatMessages.innerHTML = '';
    
    // Add all messages from history
    data.history.forEach(msg => {
        console.log('Adding message to chat:', msg); // Debug log
        addMessageToChat(msg.role, msg.content);
    });
});

// Handle history cleared
socket.on('history_cleared', () => {
    console.log('History cleared'); // Debug log
    chatMessages.innerHTML = '';
});

// Add message to chat
function addMessageToChat(role, content) {
    console.log('Adding message:', { role, content }); // Debug log
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Load history on page load
function loadHistory() {
    console.log('Loading history...'); // Debug log
    socket.emit('load_history');
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing...'); // Debug log
    setRandomPlaceholder();
    loadHistory(); // Load history when DOM is ready

    // Ensure event listeners are added after DOM is ready
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    loadHistoryButton.addEventListener('click', loadHistory);

    clearHistoryButton.addEventListener('click', () => {
        socket.emit('clear_history');
    });

    audioButton.addEventListener('click', handleAudioButtonClick);

    // Add event listener for stop recording button
    const stopButton = document.getElementById('stopRecordingButton');
    if (stopButton) { // Check if button exists
        stopButton.addEventListener('click', handleStopRecording);
    } else {
        console.error('Stop recording button not found');
    }

    // Theme toggle event listener
    if (themeToggleButton) { // Check if button exists
        themeToggleButton.addEventListener('click', () => {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            setTheme(currentTheme === 'pip-boy' ? 'beckenbauer' : 'pip-boy');
        });
    } else {
        console.error('Theme toggle button not found');
    }

});

// Theme management
function setTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

// Load saved theme or default to pip-boy
const savedTheme = localStorage.getItem('theme') || 'pip-boy';
setTheme(savedTheme);

// Handle sending messages
function sendMessage() {
    const message = messageInput.value.trim();
    if (message) {
        // Add user message to chat
        addMessageToChat('user', message);
        
        // Clear input
        messageInput.value = '';
        
        // Create a new message div for the assistant's response
        currentMessageDiv = document.createElement('div');
        currentMessageDiv.className = 'message assistant';
        chatMessages.appendChild(currentMessageDiv);
        
        // Send message to server
        socket.emit('send_message', { message });
    }
} 