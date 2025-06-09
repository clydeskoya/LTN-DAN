from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from ollama_client import OllamaClient
import json
from datetime import datetime
import os
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional, List
from functools import wraps
import requests
from config import (
    OLLAMA_HOST,
    DEFAULT_MODEL,
    HISTORY_FILE,
    MAX_HISTORY_LENGTH,
    DEFAULT_SYSTEM_PROMPT,
    SPEECH_SERVER_URL
)
import sys
from multiprocessing import Process

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = ['OLLAMA_HOST', 'DEFAULT_MODEL', 'HISTORY_FILE']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Missing required environment variables: {', '.join(missing_vars)}")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key')
socketio = SocketIO(app, 
                   cors_allowed_origins="*",
                   async_mode='threading',
                   logger=True,
                   engineio_logger=True)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Initialize Ollama client
client = OllamaClient()

# --- Helper Functions for JSON History ---
def load_history_from_file(filepath: str) -> List[Dict[str, Any]]:
    """Loads conversation history from a JSON file."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                history = json.load(f)
                if isinstance(history, list):
                    return history
                else:
                    logger.warning(f"History file '{filepath}' does not contain a list. Starting fresh.")
                    return []
        else:
            return []
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading history file '{filepath}': {e}")
        return [] # Return empty list on error

def save_history_to_file(filepath: str, history: List[Dict[str, Any]]) -> None:
    """Saves conversation history to a JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error(f"Error saving history file '{filepath}': {e}")
# --- End Helper Functions ---

def handle_errors(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {f.__name__}: {str(e)}", exc_info=True)
            emit('error', {'message': str(e)})
    return wrapped

def rate_limit_socket(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        try:
            with app.app_context():
                limiter.check()
            return f(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Rate limit exceeded: {str(e)}")
            emit('error', {'message': 'Rate limit exceeded. Please try again later.'})
    return wrapped

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/start_recording', methods=['POST'])
@limiter.limit("10 per minute")
def start_recording():
    try:
        logger.info("Forwarding start recording request to speech server")
        response = requests.post(f"{SPEECH_SERVER_URL}/start")
        response.raise_for_status()
        return jsonify({"status": "success", "message": "Recording started"})
    except requests.exceptions.RequestException as e:
        logger.error(f"Error starting recording: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/stop_recording', methods=['POST'])
@limiter.limit("10 per minute")
def stop_recording():
    try:
        logger.info("Forwarding stop recording request to speech server")
        response = requests.post(f"{SPEECH_SERVER_URL}/stop")
        response.raise_for_status()
        return jsonify({"status": "success", "message": "Recording stopped"})
    except requests.exceptions.RequestException as e:
        logger.error(f"Error stopping recording: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/check_recording_status', methods=['GET'])
@limiter.limit("10 per minute")
def check_recording_status():
    try:
        logger.info("Checking recording status from speech server")
        response = requests.get(f"{SPEECH_SERVER_URL}/status")
        response.raise_for_status()
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        logger.error(f"Error checking recording status: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@socketio.on('connect')
def handle_connect():
    logger.info("Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    logger.info("Client disconnected")

@socketio.on('send_message')
@handle_errors
@rate_limit_socket
def handle_message(data: Dict[str, Any]) -> None:
    message = data.get('message')
    if not message:
        raise ValueError("No message provided")
    
    logger.info(f"Received message: {message[:50]}...")
    response_stream = client.chat(message, stream=True)
    
    # Initialize an empty string to accumulate the response
    full_response = ""
    last_emit_time = datetime.now()
    
    for chunk in response_stream:
        if chunk:
            # Accumulate the response
            full_response += chunk
            
            # Only emit if enough time has passed (e.g., 100ms) or if it's the last chunk
            current_time = datetime.now()
            if (current_time - last_emit_time).total_seconds() >= 0.1 or not chunk:
                emit('receive_message', {
                    'role': 'assistant',
                    'content': full_response
                })
                last_emit_time = current_time
    
    # After the stream is complete, emit the final message with timestamp
    emit('receive_message', {
        'role': 'assistant',
        'content': full_response,
        'timestamp': datetime.now().isoformat()
    })
    
    # Save history after each interaction
    client.save_history()
    logger.info("Message processed and history saved")

@socketio.on('load_history')
@handle_errors
@rate_limit_socket
def handle_load_history() -> None:
    logger.info("Loading conversation history")
    try:
        client.load_history()
        history = client.get_history()
        logger.info(f"Loaded {len(history)} messages from history")
        
        # Log each message for debugging
        for msg in history:
            logger.debug(f"History message: {msg.role} - {msg.content[:50]}...")
        
        emit('history_loaded', {
            'history': [
                {
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                }
                for msg in history
            ]
        })
    except Exception as e:
        logger.error(f"Error loading history: {str(e)}", exc_info=True)
        emit('error', {'message': f"Error loading history: {str(e)}"})

@socketio.on('clear_history')
@handle_errors
@rate_limit_socket
def handle_clear_history() -> None:
    logger.info("Clearing conversation history")
    client.clear_history()
    emit('history_cleared')
    logger.info("History cleared successfully")

# --- New Endpoint for Incoming Messages ---
@app.route('/api/message', methods=['POST'])
@limiter.limit("60 per minute") # Example rate limit, adjust as needed
def handle_incoming_message():
    """Handles incoming POST requests with message data."""
    if not request.is_json:
        logger.warning("Received non-JSON request to /api/message")
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    logger.info(f"Received message data: {data}")  # Add logging to see incoming data
    
    # Handle both formats: with 'type' or with 'role'
    if 'type' in data:
        content = data.get('content')
        role = data.get('type')
    else:
        content = data.get('content')
        role = data.get('role')
    
    if not content or not role:
        logger.warning(f"Missing required fields in message: {data}")
        return jsonify({"status": "error", "message": "Missing required fields"}), 400

    new_message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }

    # Load current history, append, and save
    history = load_history_from_file(HISTORY_FILE)
    history.append(new_message)
    save_history_to_file(HISTORY_FILE, history)

    # Emit the message to all connected clients via Socket.IO
    socketio.emit('receive_message', new_message)
    logger.info(f"Emitted message via Socket.IO: {new_message}")

    # Return success response without making any HTTP requests
    return jsonify({"status": "success", "message": "Message received and stored"}), 200

def run_port_3000_server():
    """Run a simple Flask server on port 3000 to receive messages."""
    port_3000_app = Flask(__name__)
    
    @port_3000_app.route('/api/message', methods=['POST'])
    def handle_port_3000_message():
        if not request.is_json:
            logger.warning("Received non-JSON request on port 3000")
            return jsonify({"status": "error", "message": "Request must be JSON"}), 400

        data = request.get_json()
        logger.info(f"Received message on port 3000: {data}")
        
        # Handle both formats: with 'type' or with 'role'
        if 'type' in data:
            content = data.get('content')
            role = data.get('type')
        else:
            content = data.get('content')
            role = data.get('role')
        
        if not content or not role:
            logger.warning(f"Missing required fields in message: {data}")
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        new_message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }

        # Load current history, append, and save
        history = load_history_from_file(HISTORY_FILE)
        history.append(new_message)
        save_history_to_file(HISTORY_FILE, history)

        # Forward the message to the main server on port 5000
        try:
            response = requests.post(
                'http://localhost:5000/api/message',
                json=new_message,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
            logger.info("Successfully forwarded message to main server")
            return jsonify({"status": "success", "message": "Message received and stored"}), 200
        except requests.exceptions.RequestException as e:
            logger.error(f"Error forwarding message to main server: {str(e)}")
            return jsonify({"status": "error", "message": "Failed to forward message"}), 500

    try:
        logger.info("Starting port 3000 server")
        port_3000_app.run(host='0.0.0.0', port=3000, debug=False)
    except Exception as e:
        logger.error(f"Failed to start port 3000 server: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    # Start port 3000 server in a separate process
    port_3000_process = Process(target=run_port_3000_server)
    port_3000_process.start()
    logger.info("Started server on port 3000")

    try:
        # Run the main server (Socket.IO)
        logger.info("Starting main server on port 5000")
        socketio.run(app, 
                    host='0.0.0.0', 
                    port=5000, 
                    debug=False,
                    allow_unsafe_werkzeug=True)
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        port_3000_process.terminate()
        port_3000_process.join() 