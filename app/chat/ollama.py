import os
import json
import asyncio
import requests
from typing import Optional, AsyncGenerator, List, Dict
from app.chat.base import ModelProvider


class OllamaModel(ModelProvider):
    """Model provider using Ollama REST API."""

    def __init__(self, base_url: str = "http://localhost:11434", model: Optional[str] = None):
        self.base_url = base_url
        self.model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:latest")

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(f"{self.base_url}/api/chat", json=payload, timeout=300)
            )
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Ollama request failed: {e}")

    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(f"{self.base_url}/api/chat", json=payload, stream=True, timeout=300)
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line.decode('utf-8'))
                        chunk = data.get("message", {}).get("content", "")
                        if chunk: yield chunk
                        if data.get("done"): break
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            raise RuntimeError(f"Ollama stream failed: {e}")

    async def generate_title(self, prompt: str) -> str:
        messages = [
            {"role": "system", "content": "Summarize user prompt into a 3-5 word title. Return ONLY title."},
            {"role": "user", "content": f"Prompt: {prompt}"}
        ]
        try:
            title = await self.generate(messages)
            return title.strip().strip('"').strip("'")
        except:
            return prompt[:30]
