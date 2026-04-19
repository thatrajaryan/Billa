from abc import ABC, abstractmethod
from typing import AsyncGenerator


class Chat(ABC):
    """Abstract base class for chat implementations."""

    @abstractmethod
    async def send_message(self, message: str, session_id: str, context: str | None = None) -> str:
        """
        Send a message and get a response.

        Args:
            message: The user's input message
            session_id: The chat session identifier
            context: Optional context from task.md file

        Returns:
            The assistant's response
        """
        pass

    @abstractmethod
    async def send_message_stream(self, message: str, session_id: str, context: str | None = None) -> AsyncGenerator[str, None]:
        """
        Send a message and stream the response.

        Args:
            message: The user's input message
            session_id: The chat session identifier
            context: Optional context from task.md file

        Yields:
            Chunks of the assistant's response
        """
        pass
