import os
import json
import re
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator
from app.chat.base import Chat, ModelProvider
from app.chat.checkpoint_manager import CheckpointManager


class ChatService(Chat):
    """Main chat service that handles business logic and delegates to model providers."""

    def __init__(self, provider: ModelProvider, project_root: str = ".", assistant_file: Optional[str] = None):
        self.provider = provider
        self.project_root = Path(project_root)
        self.assistant_file_path = Path(assistant_file) if assistant_file else self.project_root / "assistant.md"
        self.soul_file = self.project_root / "SOUL.md"
        self.files_dir = self.project_root / "files"
        self.checkpoint_manager = CheckpointManager(os.path.join(project_root, "checkpoints"))
        self._ensure_files_dir_exists()

    def _ensure_files_dir_exists(self):
        """Create the files directory if it doesn't exist."""
        self.files_dir.mkdir(parents=True, exist_ok=True)

    def _extract_and_save_files(self, response_text: str):
        """Extract code blocks from response and save them to files/ directory."""
        pattern = r'(\S+\.\w+)\s*\n\s*```(\w*)\s*\n([\s\S]*?)```'
        matches = re.findall(pattern, response_text)
        
        for filename, language, code in matches:
            filename = filename.strip().rstrip(':')
            if '/' in filename or '\\' in filename or filename.startswith('.'):
                continue
            
            file_path = self.files_dir / filename
            try:
                file_path.write_text(code.strip())
                print(f"[ChatService] Saved file: {file_path}")
            except Exception as e:
                print(f"[ChatService] Failed to save file {filename}: {e}")

    def _load_soul_prompt(self) -> str:
        """Load the SOUL.md file for personality and rules."""
        if self.soul_file.exists():
            return self.soul_file.read_text()
        return ""

    def _build_system_prompt(self, task_context: Optional[str] = None) -> str:
        """Build system prompt from SOUL.md and task context."""
        prompt_parts = []
        soul = self._load_soul_prompt()
        if soul:
            prompt_parts.append(soul)
        if task_context:
            prompt_parts.append(f"# Current Task Context\n\n{task_context}")
        return "\n\n".join(prompt_parts)

    def _get_assistant_summary(self) -> str:
        """Get a summary from assistant.md file."""
        if not self.assistant_file_path.exists():
            return ""

        content = self.assistant_file_path.read_text()
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

    def _is_research_request(self, message: str, context: Optional[str]) -> bool:
        """Detect if this is a research request."""
        keywords = ['research', 'learn', 'study', 'deep dive', 'understand', 'explain', 'tutorial', 'guide']
        message_lower = message.lower()
        if any(kw in message_lower for kw in keywords):
            return True
        if context and "research" in context.lower():
            return True
        return False

    async def send_message(self, message: str, session_id: str, context: Optional[str] = None) -> str:
        """Send a message and get response."""
        system_prompt = self._get_assistant_summary() if session_id == "assistant" else self._build_system_prompt(context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response_text = await self.provider.generate(messages)
        self._extract_and_save_files(response_text)
        return response_text

    async def send_message_stream(self, message: str, session_id: str, context: Optional[str] = None) -> AsyncGenerator[str, None]:
        """Send a message and stream response, handling research loop if needed."""
        message_lower = message.lower().strip()
        is_continue = message_lower in ["continue", "resume", "go on", "keep going", "..."]
        checkpoint = self.checkpoint_manager.load_checkpoint(session_id)

        if self._is_research_request(message, context) or (is_continue and checkpoint and checkpoint.get("type") == "research"):
            async for chunk in self._research_loop(message, session_id, context, checkpoint):
                yield chunk
        else:
            async for chunk in self._standard_stream(message, session_id, context, checkpoint):
                yield chunk

    async def _standard_stream(self, message: str, session_id: str, context: Optional[str], checkpoint: Optional[dict]) -> AsyncGenerator[str, None]:
        """Standard streaming with checkpointing."""
        message_lower = message.lower().strip()
        is_continue = message_lower in ["continue", "resume", "go on", "keep going", "..."]
        
        actual_message = message
        if is_continue and checkpoint and checkpoint.get("type") == "standard":
            partial_content = checkpoint.get("content", "")
            actual_message = (
                f"The previous response was interrupted. Here is what was generated so far:\n\n"
                f"{partial_content}\n\n"
                f"Please continue exactly from where it left off. Do not repeat the previous content."
            )
            yield f"[Resuming from checkpoint...]\n"

        system_prompt = self._get_assistant_summary() if session_id == "assistant" else self._build_system_prompt(context)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": actual_message}
        ]

        full_response = ""
        try:
            async for chunk in self.provider.generate_stream(messages):
                full_response += chunk
                yield chunk
            
            if full_response:
                combined_response = full_response
                if is_continue and checkpoint:
                    combined_response = checkpoint.get("content", "") + full_response
                self._extract_and_save_files(combined_response)
                self.checkpoint_manager.clear_checkpoint(session_id)
        except GeneratorExit:
            # User stopped the session (closed connection)
            print(f"[ChatService] User stopped session: {session_id}")
            # If they stopped it, we shouldn't force a resume next time
            self.checkpoint_manager.clear_checkpoint(session_id)
            raise 
        except Exception as e:
            print(f"[ChatService] Stream error: {e}")
            
            if full_response:
                combined_content = full_response
                if is_continue and checkpoint:
                    combined_content = checkpoint.get("content", "") + full_response
                
                self.checkpoint_manager.save_checkpoint(session_id, {
                    "type": "standard",
                    "content": combined_content,
                    "original_message": message
                })
                yield f"\n\n[Stream Interrupted: {e}]\n"
                yield f"💡 **Tip**: Type \"continue\" to resume."
            else:
                # No output was generated, just return the error
                yield f"\n\n❌ **Error**: {str(e)}"

    async def _research_loop(self, message: str, session_id: str, context: Optional[str], checkpoint: Optional[dict]) -> AsyncGenerator[str, None]:
        """Multi-stage agentic research loop."""
        message_lower = message.lower().strip()
        is_continue = message_lower in ["continue", "resume", "go on", "keep going", "..."]

        if is_continue and checkpoint and checkpoint.get("type") == "research":
            yield "### 🔄 Resuming ChaturAI Research Protocol\n\n"
            stage = checkpoint.get("stage")
            explore_results = checkpoint.get("explore_results", "")
            roadmap = checkpoint.get("roadmap", [])
            final_markdown = checkpoint.get("final_markdown", f"# Research: {checkpoint.get('original_message', message)}\n\n")
            start_chapter = checkpoint.get("chapter_index", 0)
        else:
            yield "### 🔍 ChaturAI Research Protocol: Initiated\n\n"
            stage = "init"
            explore_results = ""
            roadmap = []
            final_markdown = f"# Research: {message}\n\n"
            start_chapter = 0
            self.checkpoint_manager.save_checkpoint(session_id, {"type": "research", "stage": "init", "original_message": message, "context": context})

        try:
            # Stage 1: Explore
            if stage == "init":
                yield "1. **Exploring** the topic... "
                instruction = f"Perform an initial deep exploration for the topic: {message}. Gather all relevant facts. Provide a comprehensive summary."
                explore_results = await self.provider.generate([{"role": "system", "content": self._build_system_prompt(context)}, {"role": "user", "content": instruction}])
                stage = "explore_done"
                self.checkpoint_manager.save_checkpoint(session_id, {"type": "research", "stage": "explore_done", "explore_results": explore_results, "original_message": message})
                yield "✅ Done.\n"

            # Stage 2: Roadmap
            if stage == "explore_done":
                yield "2. **Creating a learning roadmap**... "
                instruction = f"Based on these findings, create a detailed sequential roadmap for a learning resource. Return STRICTLY as a JSON list of objects with 'title' and 'description'.\n\nFindings:\n{explore_results}"
                response = await self.provider.generate([{"role": "system", "content": self._load_soul_prompt()}, {"role": "user", "content": instruction}])
                
                try:
                    json_match = re.search(r'\[\s*\{.*\}\s*\]', response, re.DOTALL)
                    roadmap = json.loads(json_match.group(0)) if json_match else json.loads(response)
                except:
                    roadmap = [{"title": "Overview", "description": "General introduction."}]
                
                stage = "roadmap_done"
                self.checkpoint_manager.save_checkpoint(session_id, {"type": "research", "stage": "roadmap_done", "explore_results": explore_results, "roadmap": roadmap, "original_message": message})
                yield f"✅ Created {len(roadmap)} chapters.\n\n"
                for i, ch in enumerate(roadmap): yield f"- Chapter {i+1}: {ch.get('title', 'Untitled')}\n"
                yield "\n---\n\n"
                final_markdown += f"## Research Findings (Initial)\n{explore_results}\n\n"

            # Stage 3: Chapters
            for i in range(start_chapter, len(roadmap)):
                chapter = roadmap[i]
                ch_title = chapter.get('title', f'Chapter {i+1}')
                yield f"### 📝 Processing Chapter {i+1}: {ch_title}\n"
                
                # Write
                yield "   - Writing content... "
                instruction = f"Write chapter: {ch_title}. Description: {chapter['description']}. Context: Part of roadmap {json.dumps(roadmap)}. Previous: {final_markdown[:500]}. Findings: {explore_results[:1000]}. Follow SOUL.md rules."
                content = await self.provider.generate([{"role": "system", "content": self._load_soul_prompt()}, {"role": "user", "content": instruction}])
                yield "✅\n"
                
                # Audit
                yield "   - Auditing terms... "
                instruction = f"Review this chapter. Identify terms not fully explained for beginners. Provide clear explanations for them. Return ONLY additional supplemental sections.\n\nContent:\n{content}"
                audit_additions = await self.provider.generate([{"role": "system", "content": self._load_soul_prompt()}, {"role": "user", "content": instruction}])
                yield "✅\n\n"
                
                chapter_content = f"## {ch_title}\n\n{content}\n\n### 💡 Supplemental Explanations\n{audit_additions}\n\n"
                final_markdown += chapter_content
                yield chapter_content
                yield "\n---\n\n"

                self.checkpoint_manager.save_checkpoint(session_id, {"type": "research", "stage": "chapter_done", "chapter_index": i + 1, "explore_results": explore_results, "roadmap": roadmap, "final_markdown": final_markdown, "original_message": message})

            # Stage 4: Saving
            yield "4. **Finalizing and saving**... "
            filename = f"research_{session_id}_{int(asyncio.get_event_loop().time())}.md"
            (self.files_dir / filename).write_text(final_markdown)
            self.checkpoint_manager.clear_checkpoint(session_id)
            yield f"✅ Saved as `{filename}`.\n\n**Research Complete!**"
        except GeneratorExit:
            print(f"[ChatService] User stopped research session: {session_id}")
            self.checkpoint_manager.clear_checkpoint(session_id)
            raise
        except Exception as e:
            yield f"\n\n❌ **Research Interrupted**: {str(e)}\n💡 Tip: Type \"continue\" to resume.\n"

    async def generate_title(self, prompt: str) -> str:
        """Generate title via provider."""
        return await self.provider.generate_title(prompt)
