from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, List, Dict


class ModelProvider(ABC):
    """Abstract base class for model providers (OpenRouter, Ollama, etc.)."""

    @abstractmethod
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        """Send messages and get a full response."""
        pass

    @abstractmethod
    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        """Send messages and stream the response."""
        pass

    @abstractmethod
    async def generate_title(self, prompt: str) -> str:
        """Generate a short title for a prompt."""
        pass


class Chat(ABC):
    """Abstract base class for chat implementations."""

    @abstractmethod
    async def send_message(self, message: str, session_id: str, context: Optional[str] = None) -> str:
        """Send a message and get a response."""
        pass

    @abstractmethod
    async def send_message_stream(self, message: str, session_id: str, context: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Send a message and stream the response."""
        pass

    @abstractmethod
    async def generate_title(self, prompt: str) -> str:
        """Generate a title for the conversation."""
        pass
