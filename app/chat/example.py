import asyncio
from app.chat.base import Chat
from typing import AsyncGenerator


class ExampleChat(Chat):
    """Example chat implementation for testing purposes."""

    async def send_message(self, message: str, session_id: str, context: str | None = None) -> str:
        """Echo the message with context info."""
        response = f"Echo: {message}"
        if context:
            response += f"\n\n[Context loaded from task file]"
        return response

    async def send_message_stream(self, message: str, session_id: str, context: str | None = None) -> AsyncGenerator[str, None]:
        """Stream the response character by character."""
        response = f"Echo: {message}"
        if context:
            response += f"\n\n[Context loaded from task file]"
        
        for char in response:
            yield char
            await asyncio.sleep(0.01)
