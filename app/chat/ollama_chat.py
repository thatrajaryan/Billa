import os
import json
import re
import asyncio
import requests
from pathlib import Path
from typing import Optional, AsyncGenerator
from app.chat.base import Chat


class OllamaChat(Chat):
    """Chat implementation using Ollama REST API."""

    def __init__(
        self, 
        project_root: str = ".", 
        assistant_file: Optional[str] = None,
        base_url: str = "http://localhost:11434"
    ):
        self.project_root = Path(project_root)
        self.assistant_file_path = Path(assistant_file) if assistant_file else self.project_root / "assistant.md"
        self.soul_file = self.project_root / "SOUL.md"
        self.files_dir = self.project_root / "files"
        self.base_url = base_url
        
        # Load environment variables manually if not already set
        self._load_env()

        self.model = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:latest")
        
        self._ensure_files_dir_exists()

    def _load_env(self):
        """Manually parse .env file if it exists and variables aren't already set."""
        env_path = self.project_root / ".env"
        if env_path.exists():
            content = env_path.read_text()
            for line in content.splitlines():
                if "=" in line and not line.startswith("#"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        key, value = parts
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
                print(f"[OllamaChat] Saved file: {file_path}")
            except Exception as e:
                print(f"[OllamaChat] Failed to save file {filename}: {e}")

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
            task_file = task_match.group(1).strip() if task_file else None
            
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

    async def send_message(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> str:
        """
        Send a message to Ollama and get the response.
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
            "stream": False
        }

        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                    timeout=300
                )
            )
            response.raise_for_status()
            data = response.json()
            
            if "message" in data and "content" in data["message"]:
                response_text = data["message"]["content"]
                # Extract and save files if any
                self._extract_and_save_files(response_text)
                return response_text
            else:
                raise RuntimeError(f"Unexpected Ollama response format: {data}")

        except Exception as e:
            print(f"[OllamaChat] Error: {e}")
            raise RuntimeError(f"Ollama request failed: {e}")

    async def send_message_stream(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a message to Ollama and stream the response.
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
        
        # Use a separate thread for the streaming request
        def stream_request():
            return requests.post(
                f"{self.base_url}/api/chat",
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
                    try:
                        data = json.loads(line.decode('utf-8'))
                        if "message" in data and "content" in data["message"]:
                            chunk = data["message"]["content"]
                            if chunk:
                                full_response += chunk
                                yield chunk
                        if data.get("done"):
                            break
                    except json.JSONDecodeError:
                        print(f"[OllamaChat] Failed to decode JSON chunk: {line}")

            # After streaming is complete, extract files
            if full_response:
                self._extract_and_save_files(full_response)

        except Exception as e:
            print(f"[OllamaChat] Stream error: {e}")
            yield f"[Error: {e}]"

    def reset_session(self):
        """Ollama sessions are stateless at the API level (history passed in messages)."""
        pass
