import asyncio
import subprocess
import json
from typing import Optional, AsyncGenerator, List, Dict
from app.chat.base import ModelProvider


class QwenModel(ModelProvider):
    """Model provider using Qwen CLI."""

    def __init__(self, project_root: str = "."):
        self.project_root = project_root
        self._ensure_qwen_available()

    def _ensure_qwen_available(self):
        try:
            subprocess.run(["qwen", "--version"], capture_output=True, text=True, timeout=5)
        except:
            raise RuntimeError("Qwen CLI not found")

    async def generate(self, messages: List[Dict[str, str]]) -> str:
        # Simplification: use the last user message and system prompt if available
        system_prompt = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        cmd = ["qwen", "-y", "-p", user_message]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        cmd.extend(["-o", "text"])

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=self.project_root))
            if result.returncode != 0:
                raise RuntimeError(f"Qwen failed: {result.stderr}")
            return result.stdout.strip() or result.stderr.strip()
        except Exception as e:
            raise RuntimeError(f"Qwen command failed: {e}")

    async def generate_stream(self, messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
        system_prompt = next((m["content"] for m in messages if m["role"] == "system"), "")
        user_message = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")

        cmd = ["qwen", "-y", "-p", user_message]
        if system_prompt:
            cmd.extend(["--system-prompt", system_prompt])
        cmd.extend(["-o", "stream-json", "--include-partial-messages"])

        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=self.project_root)

        try:
            while True:
                line = await process.stdout.readline()
                if not line: break
                line = line.decode("utf-8").strip()
                if not line: continue
                try:
                    data = json.loads(line)
                    # Handle multiple possible Qwen JSON formats
                    content = data.get("content") or data.get("text") or (data.get("delta", {}).get("content") if isinstance(data.get("delta"), dict) else None)
                    if content:
                        yield content if isinstance(content, str) else "".join(map(str, content))
                except json.JSONDecodeError:
                    if not line.startswith("{"): yield line
            await process.wait()
        except Exception as e:
            process.kill()
            raise e

    async def generate_title(self, prompt: str) -> str:
        system_prompt = "Summarize user prompt into a 3-5 word title. Return ONLY title."
        user_message = f"Prompt: {prompt}"
        cmd = ["qwen", "-y", "--system-prompt", system_prompt, "-p", user_message, "-o", "text"]
        
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, lambda: subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=self.project_root))
        if result.returncode == 0:
            return result.stdout.strip().strip('"').strip("'")
        return prompt[:30]
