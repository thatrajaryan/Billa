import os
import json
import asyncio
import requests
from typing import Optional, AsyncGenerator, List, Dict
from app.chat.base import ModelProvider


class OpenRouterModel(ModelProvider):
    """Model provider using OpenRouter REST API."""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPEN_ROUTER_API_KEY")
        self.model = model or os.environ.get("OPEN_ROUTER_MODEl") or os.environ.get("OPEN_ROUTER_MODEL")
        
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY not found in environment")
        if not self.model:
            raise ValueError("OPEN_ROUTER_MODEL not found in environment")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/google-deepmind/antigravity",
            "X-Title": "Antigravity Researcher"
        }

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        payload = {
            "model": self.model,
            "messages": messages
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=300
                )
            )
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                return data["choices"][0]["message"]["content"]
            else:
                raise RuntimeError(f"Unexpected OpenRouter response format: {data}")

        except Exception as e:
            print(f"[OpenRouterModel] Error: {e}")
            raise RuntimeError(f"OpenRouter request failed: {e}")

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
                lambda: requests.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                    stream=True,
                    timeout=300
                )
            )
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8')
                    if line_text.startswith("data: "):
                        content = line_text[6:].strip()
                        if content == "[DONE]":
                            break
                        
                        try:
                            data = json.loads(content)
                            if "choices" in data and len(data["choices"]) > 0:
                                delta = data["choices"][0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            print(f"[OpenRouterModel] Stream error: {e}")
            raise

    async def generate_title(self, prompt: str) -> str:
        system_prompt = "Summarize the prompt into a 3-5 word title. Return ONLY the title text."
        user_message = f"Prompt: {prompt}"
        
        try:
            title = await self.generate([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ])
            return title.strip().strip('"').strip("'").rstrip('.')
        except Exception as e:
            print(f"[OpenRouterModel] Title generation failed: {e}")
            return prompt[:30] + "..."
