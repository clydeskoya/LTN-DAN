import json
import requests
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Union

from config import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    HISTORY_FILE,
    MAX_HISTORY_LENGTH,
    OLLAMA_HOST,
)

@dataclass
class Message:
    role: str
    content: str
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_HOST):
        self.base_url = base_url
        self.model = DEFAULT_MODEL
        self.history = []
        self.system_prompt = DEFAULT_SYSTEM_PROMPT

    def set_model(self, model: str) -> None:
        """Set the model to use."""
        self.model = model

    def chat(self, message: str, system_prompt: Optional[str] = None, stream: bool = True) -> Union[str, Generator[str, None, None]]:
        """
        Send a message and get response.
        
        Args:
            message: The message to send
            system_prompt: Optional system prompt to use
            stream: Whether to stream the response
            
        Returns:
            The response from the model
        """
        # Add user message to history
        self.history.append(Message(role='user', content=message))
        
        # Prepare the request
        url = f"{self.base_url}/api/chat"
        headers = {'Content-Type': 'application/json'}
        
        # Prepare messages for the API
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        else:
            messages.append({'role': 'system', 'content': self.system_prompt})
            
        # Add history messages
        for msg in self.history:
            messages.append({'role': msg.role, 'content': msg.content})
        
        data = {
            'model': self.model,
            'messages': messages,
            'stream': stream
        }
        
        if stream:
            return self._stream_chat(url, headers, data)
        else:
            return self._regular_chat(url, headers, data)

    def _regular_chat(self, url: str, headers: Dict, data: Dict) -> str:
        """Handle regular (non-streaming) chat requests."""
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        
        result = response.json()
        assistant_message = result['message']['content']
        
        # Add assistant message to history
        self.history.append(Message(role='assistant', content=assistant_message))
        
        # Trim history if it exceeds max length
        if len(self.history) > MAX_HISTORY_LENGTH:
            self.history = self.history[-MAX_HISTORY_LENGTH:]
            
        return assistant_message

    def _stream_chat(self, url: str, headers: Dict, data: Dict) -> Generator[str, None, None]:
        """Handle streaming chat requests."""
        response = requests.post(url, headers=headers, json=data, stream=True)
        response.raise_for_status()
        
        current_message = ""
        
        for line in response.iter_lines():
            if line:
                try:
                    result = json.loads(line)
                    if 'message' in result and 'content' in result['message']:
                        chunk = result['message']['content']
                        current_message += chunk
                        yield chunk
                except json.JSONDecodeError:
                    continue
        
        # Add complete assistant message to history
        if current_message:
            self.history.append(Message(role='assistant', content=current_message))
            
            # Trim history if it exceeds max length
            if len(self.history) > MAX_HISTORY_LENGTH:
                self.history = self.history[-MAX_HISTORY_LENGTH:]

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.history = []

    def get_history(self) -> List[Message]:
        """Get the current conversation history."""
        return self.history

    def save_history(self, filepath: str = HISTORY_FILE) -> None:
        """
        Save the conversation history to a file.
        
        Args:
            filepath: Path to save the history (defaults to HISTORY_FILE)
        """
        history_data = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat()
            }
            for msg in self.history
        ]
        
        with open(filepath, 'w') as f:
            json.dump(history_data, f, indent=2)

    def load_history(self, filepath: str = HISTORY_FILE) -> None:
        """
        Load conversation history from a file.
        
        Args:
            filepath: Path to load the history from (defaults to HISTORY_FILE)
        """
        with open(filepath, 'r') as f:
            history_data = json.load(f)
        
        self.history = [
            Message(
                role=msg["role"],
                content=msg["content"],
                timestamp=datetime.fromisoformat(msg["timestamp"])
            )
            for msg in history_data
        ]  
        # Trim history if it exceeds max length
        if len(self.history) > MAX_HISTORY_LENGTH:
            self.history = self.history[-MAX_HISTORY_LENGTH:] 