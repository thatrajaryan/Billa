import asyncio
import subprocess
import os
import json
import re
from pathlib import Path
from typing import Optional, AsyncGenerator
from app.chat.base import Chat


class QwenChat(Chat):
    """Chat implementation using Qwen CLI with process lifecycle management."""

    def __init__(self, project_root: str = ".", assistant_file: Optional[str] = None):
        self.project_root = Path(project_root)
        self.assistant_file_path = Path(assistant_file) if assistant_file else self.project_root / "assistant.md"
        self.soul_file = self.project_root / "SOUL.md"
        self.files_dir = self.project_root / "files"
        self.current_process: Optional[subprocess.Popen] = None
        self.current_session_id: Optional[str] = None
        self.current_task_file: Optional[str] = None

        # Initialize
        self._ensure_qwen_available()
        self._ensure_files_dir_exists()

    def _ensure_qwen_available(self):
        """Check if Qwen CLI is available."""
        try:
            result = subprocess.run(
                ["qwen", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RuntimeError("Qwen CLI is not available")
        except FileNotFoundError:
            raise RuntimeError("Qwen CLI not found. Please install it first.")

    def _ensure_files_dir_exists(self):
        """Create the files directory if it doesn't exist."""
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _extract_and_save_files(self, response_text: str):
        """
        Extract code blocks from response and save them to files/ directory.
        Looks for patterns like: filename.ext\n```language\ncode\n```
        """
        # Pattern to match filename followed by code block
        # Matches: filename.py\n```python\ncode\n```
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
            file_path.write_text(code.strip())
            print(f"[QwenChat] Saved file: {file_path}")

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
            if task_file and Path(task_file).exists():
                task_content = Path(task_file).read_text()
                task_summary_match = re.search(r"^#\s+.+$\n\n(.*?)(?=^##\s)", task_content, re.MULTILINE | re.DOTALL)
                if task_summary_match:
                    summary = task_summary_match.group(1).strip()
                    if len(summary) > 100:
                        summary = summary[:100] + "..."
                    summary_parts.append(summary)
            
            summary_parts.append("")

        return "\n".join(summary_parts)

    async def _run_qwen_command(
        self,
        message: str,
        session_id: str,
        task_context: Optional[str] = None,
        stream: bool = False
    ) -> str:
        """
        Run a Qwen CLI command.

        Args:
            message: User message
            session_id: Session identifier
            task_context: Optional task context
            stream: Whether to stream the response

        Returns:
            Response text
        """
        # Build command
        cmd = ["qwen", "-y"]

        # For "assistant" session, provide summary of all conversations
        if session_id == "assistant":
            assistant_summary = self._get_assistant_summary()
            if assistant_summary:
                cmd.extend(["--append-system-prompt", assistant_summary])
        elif task_context:
            # For specific sessions, use the task context
            cmd.extend(["--system-prompt", self._build_system_prompt(task_context)])

        # Handle session continuation (only for non-assistant sessions)
        if self.current_session_id == session_id and session_id != "assistant":
            cmd.append("--continue")

        self.current_session_id = session_id
        self.current_task_file = task_context

        # Add prompt
        cmd.extend(["-p", message])

        # Add output format - use text for simplicity
        if stream:
            cmd.extend(["-o", "stream-json", "--include-partial-messages"])
        else:
            cmd.extend(["-o", "text"])

        # Run command
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,  # 5 minute timeout
                    cwd=str(self.project_root)
                )
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                print(f"[QwenChat] Command failed: {error_msg}")
                raise RuntimeError(f"Qwen command failed: {error_msg}")

            # Return the text output
            response_text = result.stdout.strip()
            if not response_text:
                response_text = result.stderr.strip()

            print(f"[QwenChat] Response length: {len(response_text)}")

            # Check for file creation requests in the response
            self._extract_and_save_files(response_text)

            return response_text

        except subprocess.TimeoutExpired:
            raise RuntimeError("Qwen command timed out")

    async def _run_qwen_command_stream(
        self,
        message: str,
        session_id: str,
        task_context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Run a Qwen CLI command with true streaming.

        Args:
            message: User message
            session_id: Session identifier
            task_context: Optional task context

        Yields:
            Text chunks as they arrive from Qwen
        """
        # Build command
        cmd = ["qwen", "-y"]

        # For "assistant" session, provide summary of all conversations
        if session_id == "assistant":
            assistant_summary = self._get_assistant_summary()
            if assistant_summary:
                cmd.extend(["--append-system-prompt", assistant_summary])
        elif task_context:
            # For specific sessions, use the task context
            cmd.extend(["--system-prompt", self._build_system_prompt(task_context)])

        # Handle session continuation (only for non-assistant sessions)
        if self.current_session_id == session_id and session_id != "assistant":
            cmd.append("--continue")

        self.current_session_id = session_id
        self.current_task_file = task_context

        # Add prompt
        cmd.extend(["-p", message])

        # Use stream-json output format
        cmd.extend(["-o", "stream-json", "--include-partial-messages"])

        print(f"[QwenChat] Starting stream with command: {' '.join(cmd)}")

        # Start the process
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_root)
        )

        self.current_process = process

        full_response = ""

        try:
            # Read stdout line by line
            while True:
                line = await process.stdout.readline()
                if not line:
                    break

                line = line.decode("utf-8").strip()
                if not line:
                    continue

                # Parse JSON lines from stream-json output
                # Qwen stream-json format typically contains lines like:
                # {"type": "chunk", "content": "..."}
                # or similar JSON structures
                try:
                    data = json.loads(line)

                    # Extract text content from various possible JSON structures
                    chunk_text = None

                    # Common patterns for Qwen stream output
                    if "content" in data:
                        content = data["content"]
                        if isinstance(content, list):
                            chunk_text = "".join(str(c) for c in content)
                        elif isinstance(content, str):
                            chunk_text = content
                        else:
                            chunk_text = str(content)
                    elif "text" in data:
                        text = data["text"]
                        if isinstance(text, list):
                            chunk_text = "".join(str(t) for t in text)
                        else:
                            chunk_text = str(text)
                    elif "delta" in data:
                        delta = data["delta"]
                        if isinstance(delta, dict):
                            content = delta.get("content", delta.get("text", ""))
                            if isinstance(content, list):
                                chunk_text = "".join(str(c) for c in content)
                            else:
                                chunk_text = str(content)
                        else:
                            chunk_text = str(delta)
                    elif "message" in data:
                        message_data = data["message"]
                        if isinstance(message_data, dict):
                            content = message_data.get("content", "")
                            if isinstance(content, list):
                                chunk_text = "".join(str(c) for c in content)
                            else:
                                chunk_text = str(content)
                        else:
                            chunk_text = str(message_data)
                    elif "choices" in data:
                        # OpenAI-compatible format
                        choices = data["choices"]
                        if choices and isinstance(choices, list):
                            choice = choices[0]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if isinstance(content, list):
                                chunk_text = "".join(str(c) for c in content)
                            else:
                                chunk_text = str(content)

                    if chunk_text:
                        full_response += chunk_text
                        yield chunk_text

                except json.JSONDecodeError:
                    # If not JSON, might be plain text chunk
                    if line and not line.startswith("{"):
                        full_response += line
                        yield line

            # Wait for process to complete
            await process.wait()

            # Check for errors
            if process.returncode != 0:
                stderr_output = ""
                if process.stderr:
                    stderr_output = await process.stderr.read()
                    stderr_output = stderr_output.decode("utf-8").strip()

                if stderr_output:
                    print(f"[QwenChat] Stream error: {stderr_output}")
                    if not full_response:  # Only yield error if no response yet
                        yield f"[Error: {stderr_output}]"
                return

            print(f"[QwenChat] Stream completed. Total length: {len(full_response)}")

            # Check for file creation requests in the response
            if full_response:
                self._extract_and_save_files(full_response)

        except asyncio.CancelledError:
            print("[QwenChat] Stream cancelled")
            process.kill()
            raise
        except Exception as e:
            print(f"[QwenChat] Stream exception: {e}")
            process.kill()
            raise
        finally:
            self.current_process = None

    def _kill_current_process(self):
        """Kill the current Qwen process if running."""
        if self.current_process and self.current_process.poll() is None:
            self.current_process.terminate()
            try:
                self.current_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.current_process.kill()
            self.current_process = None

    async def send_message(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> str:
        """
        Send a message to Qwen and get the response.

        Args:
            message: User message
            session_id: Session identifier
            context: Task context (task.md content)

        Returns:
            Qwen's response
        """
        return await self._run_qwen_command(
            message=message,
            session_id=session_id,
            task_context=context,
            stream=False
        )

    async def send_message_stream(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a message to Qwen and stream the response in real-time.

        Args:
            message: User message
            session_id: Session identifier
            context: Task context (task.md content)

        Yields:
            Chunks of the assistant's response as they arrive
        """
        async for chunk in self._run_qwen_command_stream(
            message=message,
            session_id=session_id,
            task_context=context
        ):
            yield chunk

    def reset_session(self):
        """Reset the current session and kill any running process."""
        self._kill_current_process()
        self.current_session_id = None
        self.current_task_file = None

    async def generate_title(self, prompt: str) -> str:
        """Generate a concise title (3-5 words) for a conversation based on the initial prompt."""
        system_prompt = "You are a helpful assistant that summarizes user prompts into very concise, 3-5 word titles. Return only the title text, nothing else. Do not use quotes."
        user_message = f"Summarize this prompt into a 3-5 word title: {prompt}"
        
        try:
            # Run Qwen CLI once for the title
            cmd = ["qwen", "-y", "--system-prompt", system_prompt, "-p", user_message, "-o", "text"]
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=str(self.project_root)
                )
            )
            
            if result.returncode == 0:
                title = result.stdout.strip().strip('"').strip("'").rstrip('.')
                if not title:
                    title = result.stderr.strip().strip('"').strip("'").rstrip('.')
                return title if title else prompt[:30] + "..."
            return prompt[:30] + "..."
        except Exception as e:
            print(f"[QwenChat] Failed to generate title: {e}")
            return prompt[:30] + "..."
