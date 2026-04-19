import os
import json
import re
import asyncio
import requests
from pathlib import Path
from typing import Optional, AsyncGenerator
from app.chat.base import Chat


class OpenRouterChat(Chat):
    """Chat implementation using OpenRouter REST API."""

    def __init__(self, project_root: str = ".", assistant_file: Optional[str] = None):
        self.project_root = Path(project_root)
        self.assistant_file_path = Path(assistant_file) if assistant_file else self.project_root / "assistant.md"
        self.soul_file = self.project_root / "SOUL.md"
        self.files_dir = self.project_root / "files"
        
        # Load environment variables manually if not already set
        self._load_env()

        self.api_key = os.environ.get("OPEN_ROUTER_API_KEY")
        # Support both the typo "MODEl" and "MODEL"
        self.model = os.environ.get("OPEN_ROUTER_MODEl") or os.environ.get("OPEN_ROUTER_MODEL")
        
        if not self.api_key:
            raise ValueError("OPEN_ROUTER_API_KEY not found in environment or .env file")
        if not self.model:
            raise ValueError("OPEN_ROUTER_MODEl (or MODEL) not found in environment or .env file")

        self._ensure_files_dir_exists()

    def _load_env(self):
        """Manually parse .env file if it exists and variables aren't already set."""
        env_path = self.project_root / ".env"
        if env_path.exists():
            content = env_path.read_text()
            for line in content.splitlines():
                if "=" in line and not line.startswith("#"):
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key not in os.environ:
                        os.environ[key] = value

    def _ensure_files_dir_exists(self):
        """Create the files directory if it doesn't exist."""
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _extract_and_save_files(self, response_text: str):
        """
        Extract code blocks from response and save them to files/ directory.
        Looks for patterns like: filename.ext\n```language\ncode\n```
        """
        # Pattern to match filename followed by code block
        pattern = r'(\S+\.\w+)\s*\n\s*```(\w*)\s*\n([\s\S]*?)```'
        
        matches = re.findall(pattern, response_text)
        
        for filename, language, code in matches:
            # Clean up filename
            filename = filename.strip().rstrip(':')
            
            # Only save if it's a reasonable filename (no path traversal)
            if '/' in filename or '\\' in filename or filename.startswith('.'):
                continue
            
            # Save to files directory using absolute path
            file_path = self.files_dir / filename
            try:
                file_path.write_text(code.strip())
                print(f"[OpenRouterChat] Saved file: {file_path}")
            except Exception as e:
                print(f"[OpenRouterChat] Failed to save file {filename}: {e}")

    def _load_soul_prompt(self) -> str:
        """Load the SOUL.md file for personality and rules."""
        if self.soul_file.exists():
            return self.soul_file.read_text()
        return ""

    def _build_system_prompt(self, task_context: Optional[str] = None) -> str:
        """Build system prompt from SOUL.md and task context."""
        prompt_parts = []

        # Always start with SOUL.md for personality
        soul = self._load_soul_prompt()
        if soul:
            prompt_parts.append(soul)

        # Add task context if provided
        if task_context:
            prompt_parts.append(f"# Current Task Context\n\n{task_context}")

        return "\n\n".join(prompt_parts)

    def _get_assistant_summary(self) -> str:
        """Get a summary from assistant.md file."""
        if not self.assistant_file_path.exists():
            return ""

        content = self.assistant_file_path.read_text()
        
        # Build a summary of all sessions
        session_pattern = r"##\s+(.+?)\s*\n((?:-.*\n)*)"
        sessions = re.findall(session_pattern, content, re.MULTILINE)

        if not sessions:
            return ""

        summary_parts = ["# Active Conversations\n"]
        for session_id, details in sessions:
            task_match = re.search(r"Task:\s*(.+?\.md)", details)
            title_match = re.search(r"Title:\s*(.+)", details)
            
            title = title_match.group(1).strip() if title_match else session_id
            task_file = task_match.group(1).strip() if task_match else None
            
            summary_parts.append(f"## {title}")
            if task_file:
                summary_parts.append(f"Task: {task_file}")
                
            # Add task summary if available
            if task_file and (self.project_root / task_file).exists():
                task_content = (self.project_root / task_file).read_text()
                task_summary_match = re.search(r"^#\s+.+$\n\n(.*?)(?=^##\s)", task_content, re.MULTILINE | re.DOTALL)
                if task_summary_match:
                    summary = task_summary_match.group(1).strip()
                    if len(summary) > 100:
                        summary = summary[:100] + "..."
                    summary_parts.append(summary)
            
            summary_parts.append("")

        return "\n".join(summary_parts)

    def _get_headers(self) -> dict:
        """Get headers for OpenRouter API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/google-deepmind/antigravity", # Optional
            "X-Title": "Antigravity Researcher" # Optional
        }

    async def send_message(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> str:
        """
        Send a message to OpenRouter and get the response.
        """
        system_prompt = ""
        if session_id == "assistant":
            system_prompt = self._get_assistant_summary()
        else:
            system_prompt = self._build_system_prompt(context)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ]
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
                response_text = data["choices"][0]["message"]["content"]
                # Extract and save files if any
                self._extract_and_save_files(response_text)
                return response_text
            else:
                raise RuntimeError(f"Unexpected OpenRouter response format: {data}")

        except Exception as e:
            print(f"[OpenRouterChat] Error: {e}")
            raise RuntimeError(f"OpenRouter request failed: {e}")

    async def send_message_stream(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a message to OpenRouter and stream the response.
        """
        system_prompt = ""
        if session_id == "assistant":
            system_prompt = self._get_assistant_summary()
        else:
            system_prompt = self._build_system_prompt(context)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": message}
            ],
            "stream": True
        }

        full_response = ""
        
        # Use a separate thread for the streaming request since 'requests' is blocking
        def stream_request():
            return requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=self._get_headers(),
                json=payload,
                stream=True,
                timeout=300
            )

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(None, stream_request)
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
                                    full_response += chunk
                                    yield chunk
                        except json.JSONDecodeError:
                            print(f"[OpenRouterChat] Failed to decode JSON chunk: {content}")

            # After streaming is complete, extract files
            if full_response:
                self._extract_and_save_files(full_response)

        except Exception as e:
            print(f"[OpenRouterChat] Stream error: {e}")
            yield f"[Error: {e}]"

    def reset_session(self):
        """Sessions in OpenRouter are handled by history, which is managed by the caller/Assistant."""
        pass
