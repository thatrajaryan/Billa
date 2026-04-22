import os
import json
import re
import asyncio
import requests
from pathlib import Path
from typing import Optional, AsyncGenerator, List, Dict
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

    async def _make_api_call(self, system_prompt: str, user_message: str) -> str:
        """Make a single non-streaming API call to OpenRouter."""
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
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
                return data["choices"][0]["message"]["content"]
            else:
                raise RuntimeError(f"Unexpected OpenRouter response format: {data}")
        except Exception as e:
            print(f"[OpenRouterChat] API Error: {e}")
            raise

    async def _research_explore(self, message: str, context: Optional[str]) -> str:
        """Stage 1: Exploration call."""
        system_prompt = self._build_system_prompt(context)
        instruction = f"Perform an initial deep exploration for the topic: {message}. Gather all relevant facts, concepts, and technical details. Provide a comprehensive summary of your findings."
        return await self._make_api_call(system_prompt, instruction)

    async def _research_roadmap(self, exploration_results: str) -> List[Dict[str, str]]:
        """Stage 2: Roadmap Creation call."""
        system_prompt = self._load_soul_prompt()
        instruction = (
            "Based on the following research findings, create a detailed roadmap for a learning resource. "
            "Divide it into sequential chapters. Each chapter should build on the previous ones. "
            "Return the roadmap STRICTLY as a JSON list of objects, each with 'title' and 'description' keys. "
            "Example: [{\"title\": \"Intro\", \"description\": \"...\"}]\n\n"
            f"Findings:\n{exploration_results}"
        )
        response = await self._make_api_call(system_prompt, instruction)
        
        # Extract JSON from response
        try:
            # Look for JSON block
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(response)
        except Exception as e:
            print(f"[OpenRouterChat] Failed to parse roadmap JSON: {e}")
            # Fallback: simple split if JSON fails
            return [{"title": "Overview", "description": "General introduction based on findings."}]

    async def _research_write_chapter(self, chapter: Dict[str, str], roadmap: List[Dict], previous_content: str, exploration_results: str) -> str:
        """Stage 3a: Write Chapter call."""
        system_prompt = self._load_soul_prompt()
        instruction = (
            f"Write the following chapter of the learning resource: {chapter['title']}.\n"
            f"Description: {chapter['description']}\n\n"
            f"Context: This is part of a larger roadmap: {json.dumps(roadmap)}\n\n"
            f"Previous Content Summary: {previous_content[:500]}...\n\n"
            f"Research Findings: {exploration_results[:1000]}...\n\n"
            "Follow the SOUL.md rules: Assume beginner level, use detailed explanations, and reference code segments if applicable."
        )
        return await self._make_api_call(system_prompt, instruction)

    async def _research_audit_chapter(self, content: str) -> str:
        """Stage 3b: Audit & Elaborate call."""
        system_prompt = self._load_soul_prompt()
        instruction = (
            "Review the following chapter content. Identify any technical terms, acronyms, or complex concepts that might not be fully explained for a beginner. "
            "For each such term, provide a clear, detailed explanation. If the original text already explains it well, skip it. "
            "Return ONLY the additional explanations or refined sections that should be integrated. "
            "Make it feel like a natural part of the learning resource.\n\n"
            f"Content:\n{content}"
        )
        return await self._make_api_call(system_prompt, instruction)

    def _is_research_request(self, message: str, context: Optional[str]) -> bool:
        """Detect if this is a research request that warrants the multi-stage loop."""
        keywords = ['research', 'learn', 'study', 'deep dive', 'understand', 'explain', 'tutorial', 'guide']
        message_lower = message.lower()
        if any(kw in message_lower for kw in keywords):
            return True
        if context and "research" in context.lower():
            return True
        return False

    async def send_message_stream(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Send a message to OpenRouter and stream the response.
        If it's a research request, perform multi-stage agentic loop.
        """
        if not self._is_research_request(message, context):
            # Fallback to standard streaming
            async for chunk in self._standard_stream(message, session_id, context):
                yield chunk
            return

        # Start Research Loop
        yield "### 🔍 Billa Research Protocol: Initiated\n\n"
        
        try:
            # Stage 1: Explore
            yield "1. **Exploring** the topic and gathering information... "
            explore_results = await self._research_explore(message, context)
            yield "✅ Done.\n"

            # Stage 2: Roadmap
            yield "2. **Creating a learning roadmap**... "
            roadmap = await self._research_roadmap(explore_results)
            yield f"✅ Created {len(roadmap)} chapters.\n\n"
            
            yield "#### Roadmap:\n"
            for i, ch in enumerate(roadmap):
                yield f"- Chapter {i+1}: {ch.get('title', 'Untitled')}\n"
            yield "\n---\n\n"

            # Stage 3: Chapters
            final_markdown = f"# Research: {message}\n\n"
            final_markdown += f"## Research Findings (Initial)\n{explore_results}\n\n"
            
            for i, chapter in enumerate(roadmap):
                ch_title = chapter.get('title', f'Chapter {i+1}')
                yield f"### 📝 Processing Chapter {i+1}: {ch_title}\n"
                
                # Step 3a: Write
                yield "   - Writing content... "
                content = await self._research_write_chapter(chapter, roadmap, final_markdown, explore_results)
                yield "✅\n"
                
                # Step 3b: Audit
                yield "   - Auditing terms & elaborating... "
                audit_additions = await self._research_audit_chapter(content)
                yield "✅\n\n"
                
                # Integrate and yield to user
                chapter_content = f"## {ch_title}\n\n{content}\n\n### 💡 Supplemental Explanations\n{audit_additions}\n\n"
                final_markdown += chapter_content
                yield chapter_content
                yield "\n---\n\n"

            # Stage 4: Consolidation & Saving
            yield "4. **Finalizing and saving resource**... "
            filename = f"research_{session_id}_{int(asyncio.get_event_loop().time())}.md"
            file_path = self.files_dir / filename
            file_path.write_text(final_markdown)
            yield f"✅ Saved as `{filename}`.\n\n"
            
            yield f"**Research Complete!** You can download the full resource from the 📁 Files button in the sidebar: `{filename}`"

        except Exception as e:
            yield f"\n\n❌ **Research Interrupted**: {str(e)}\n"
            print(f"[OpenRouterChat] Research Loop Error: {e}")

    async def _standard_stream(
        self,
        message: str,
        session_id: str,
        context: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Original streaming logic."""
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

            if full_response:
                self._extract_and_save_files(full_response)

        except Exception as e:
            print(f"[OpenRouterChat] Stream error: {e}")
            yield f"[Error: {e}]"

    def reset_session(self):
        """Sessions in OpenRouter are handled by history, which is managed by the caller/Assistant."""
        pass
