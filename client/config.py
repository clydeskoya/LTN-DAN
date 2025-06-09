import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ollama API Configuration
OLLAMA_HOST = os.getenv('OLLAMA_HOST')
DEFAULT_MODEL = os.getenv('DEFAULT_MODEL')

# Speech to Text Configuration
SPEECH_SERVER_URL = os.getenv('SPEECH_SERVER_URL', 'http://192.168.1.147:5001')

# History Management
HISTORY_FILE = os.getenv('HISTORY_FILE', 'conversation_history.json')

# Optional Settings
MAX_HISTORY_LENGTH = int(os.getenv('MAX_HISTORY_LENGTH', '100'))
DEFAULT_SYSTEM_PROMPT = os.getenv('DEFAULT_SYSTEM_PROMPT', 'You are a helpful AI assistant.')

# Validate configuration
def validate_config():
    """Validate the configuration values."""
    if not OLLAMA_HOST.startswith(('http://', 'https://')):
        raise ValueError("OLLAMA_HOST must start with http:// or https://")
    
    if not SPEECH_SERVER_URL.startswith(('http://', 'https://')):
        raise ValueError("SPEECH_SERVER_URL must start with http:// or https://")
    
    if MAX_HISTORY_LENGTH < 1:
        raise ValueError("MAX_HISTORY_LENGTH must be greater than 0")

# Run validation when module is imported
validate_config() 