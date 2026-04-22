import os
import re
from pathlib import Path
from typing import Optional


class Assistant:
    """Manages chat sessions and their associated task contexts."""

    def __init__(self, assistant_file: str = "assistant.md", tasks_dir: str = "tasks"):
        self.assistant_file = Path(assistant_file)
        self.tasks_dir = Path(tasks_dir)
        self._ensure_file_exists()
        self._ensure_tasks_dir_exists()

    def _ensure_file_exists(self):
        """Create the assistant.md file if it doesn't exist."""
        if not self.assistant_file.exists():
            self.assistant_file.parent.mkdir(parents=True, exist_ok=True)
            self.assistant_file.write_text("# Assistant Session Mapping\n\n")

    def _ensure_tasks_dir_exists(self):
        """Create the tasks directory if it doesn't exist."""
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def get_task_context(self, session_id: str) -> Optional[str]:
        """
        Retrieve the task.md context for a given session.

        Args:
            session_id: The chat session identifier

        Returns:
            The content of the task.md file if found, None otherwise
        """
        task_file = self._find_task_file(session_id)
        if task_file and task_file.exists():
            return task_file.read_text()
        return None

    def _find_task_file(self, session_id: str) -> Optional[Path]:
        """
        Parse assistant.md to find the task.md file associated with a session.

        Expected format in assistant.md:
        ## session_name
        - Task: path/to/task.md

        Args:
            session_id: The chat session identifier

        Returns:
            Path to the task.md file if found, None otherwise
        """
        if not self.assistant_file.exists():
            return None

        content = self.assistant_file.read_text()
        
        # Pattern to match session and its task file
        pattern = rf"##\s+{re.escape(session_id)}\s*\n.*?Task:\s*(.+?\.md)"
        match = re.search(pattern, content, re.IGNORECASE)
        
        if match:
            task_path = match.group(1).strip()
            return Path(task_path)
        
        return None

    def add_session_mapping(self, session_id: str, task_file: str):
        """
        Add a new session to task mapping in assistant.md.

        Args:
            session_id: The chat session identifier
            task_file: Path to the task.md file
        """
        with open(self.assistant_file, "a") as f:
            f.write(f"\n## {session_id}\n")
            f.write(f"- Task: {task_file}\n")

    def list_sessions(self) -> list[str]:
        """
        List all registered sessions.

        Returns:
            List of session IDs
        """
        if not self.assistant_file.exists():
            return []

        content = self.assistant_file.read_text()
        pattern = r"##\s+(.+?)\s*\n"
        return re.findall(pattern, content)

    def list_tasks(self) -> list[dict]:
        """
        List all available task files with their summaries.

        Returns:
            List of dicts with task info (name, path, summary)
        """
        tasks = []
        
        if not self.tasks_dir.exists():
            return tasks

        # Find all .md files in tasks directory
        task_files = sorted(self.tasks_dir.glob("*.md"))

        for task_file in task_files:
            task_info = self._extract_task_summary(task_file)
            tasks.append(task_info)

        return tasks

    def _extract_task_summary(self, task_file: Path) -> dict:
        """
        Extract a summary from a task file.
        The summary is the content between the title and the first ## heading.

        Args:
            task_file: Path to the task markdown file

        Returns:
            Dict with task name, path, and summary
        """
        content = task_file.read_text()

        # Extract title (first # heading)
        title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else task_file.stem

        # Extract summary (content between title and first ## heading)
        summary_match = re.search(r"^#\s+.+$\n\n(.*?)(?=^##\s)", content, re.MULTILINE | re.DOTALL)
        summary = ""
        if summary_match:
            summary = summary_match.group(1).strip()
            # Limit to first 150 chars for display
            if len(summary) > 150:
                summary = summary[:150] + "..."

        return {
            "name": title,
            "path": str(task_file),
            "filename": task_file.name,
            "summary": summary
        }

    def create_new_task(self, task_name: str, initial_content: str = "") -> str:
        """
        Create a new task file in the tasks directory.

        Args:
            task_name: Name for the new task (will be converted to filename)
            initial_content: Optional initial content for the task file

        Returns:
            Path to the created task file
        """
        # Convert name to filename
        filename = task_name.lower().replace(" ", "-").replace("_", "-") + ".md"
        task_file = self.tasks_dir / filename

        # If file exists, add suffix
        counter = 1
        while task_file.exists():
            filename = f"{task_name.lower().replace(' ', '-').replace('_', '-')}-{counter}.md"
            task_file = self.tasks_dir / filename
            counter += 1

        # Create task file with default structure
        content = f"# {task_name}\n\n"
        if initial_content:
            content += initial_content
        else:
            content += f"## Summary\n- Auto-generated conversation\n\n## Instructions\n- Follow user requirements\n"

        task_file.write_text(content)
        return str(task_file)

    def add_session_mapping(self, session_id: str, task_file: str, title: str = ""):
        """
        Add a new session to task mapping in assistant.md.

        Args:
            session_id: The chat session identifier
            task_file: Path to the task.md file
            title: Optional display title for the session
        """
        with open(self.assistant_file, "a") as f:
            f.write(f"\n## {session_id}\n")
            f.write(f"- Task: {task_file}\n")
            if title:
                f.write(f"- Title: {title}\n")

    def detect_matching_session(self, message: str) -> Optional[dict]:
        """
        Detect if a message matches an existing conversation topic.
        Returns the most relevant session if found.
        
        Searches through:
        - Task file names and titles
        - Task file content and summaries
        - Session titles

        Args:
            message: The user's message to match against

        Returns:
            Dict with session_id and task_file if match found, None otherwise
        """
        if not self.assistant_file.exists():
            return None

        content = self.assistant_file.read_text()
        message_lower = message.lower()
        
        # Extract significant words from message (4+ chars, exclude common words)
        common_words = {'this', 'that', 'with', 'from', 'have', 'been', 'would', 'could', 'should', 'their', 'there', 'about', 'what', 'which', 'when', 'where', 'who', 'how', 'can', 'will', 'just', 'don', 'think', 'know', 'make', 'like', 'also', 'very', 'into', 'more', 'some', 'other', 'than', 'them', 'these', 'may', 'might', 'must', 'shall', 'need', 'dare', 'used'}
        message_words = set(re.findall(r'\b\w{4,}\b', message_lower)) - common_words

        if not message_words:
            return None

        # Parse all sessions
        session_pattern = r"##\s+(.+?)\s*\n((?:-.*\n)*)"
        sessions = re.findall(session_pattern, content, re.MULTILINE)

        best_match = None
        best_score = 0

        for session_id, details in sessions:
            # Extract task file
            task_match = re.search(r"Task:\s*(.+?\.md)", details)
            if not task_match:
                continue
                
            task_file = task_match.group(1).strip()
            task_path = Path(task_file)

            if not task_path.exists():
                continue

            task_content = task_path.read_text()
            task_content_lower = task_content.lower()
            
            # Calculate match score
            score = 0
            
            # 1. Check if task filename appears in message
            task_name = task_path.stem.lower().replace('-', ' ').replace('_', ' ')
            task_name_words = set(re.findall(r'\b\w{4,}\b', task_name))
            name_matches = message_words & task_name_words
            score += len(name_matches) * 3  # Higher weight for filename matches
            
            # 2. Check if message words appear in task content
            task_words = set(re.findall(r'\b\w{4,}\b', task_content_lower))
            content_matches = message_words & task_words
            score += len(content_matches) * 1
            
            # 3. Check for exact phrase matches (higher significance)
            # Look for 2-3 word phrases from message in task
            message_phrases = set()
            words = message_lower.split()
            for i in range(len(words) - 1):
                if i + 2 <= len(words):
                    message_phrases.add(' '.join(words[i:i+2]))
                if i + 3 <= len(words):
                    message_phrases.add(' '.join(words[i:i+3]))
            
            phrase_matches = sum(1 for phrase in message_phrases if phrase in task_content_lower)
            score += phrase_matches * 5  # Very high weight for phrase matches
            
            # 4. Check task title/header matches
            title_matches = re.findall(r'^#\s+(.+)$', task_content, re.MULTILINE)
            for title in title_matches:
                title_words = set(re.findall(r'\b\w{4,}\b', title.lower()))
                title_match_words = message_words & title_words
                score += len(title_match_words) * 4

            # Update best match if this session scores higher
            if score > best_score and score >= 3:  # Minimum threshold
                best_score = score
                best_match = {
                    "session_id": session_id,
                    "task_file": task_file,
                    "matched_keywords": list(content_matches | name_matches),
                    "score": score
                }

        return best_match

    def update_task_summary(self, session_id: str, user_message: str, assistant_response: str, summary: str) -> dict:
        """
        Update the task.md file with fresh content after each conversation turn.

        Args:
            session_id: The session identifier
            user_message: The user's latest message
            assistant_response: The assistant's response
            summary: A brief summary of the conversation

        Returns:
            Dict with success status
        """
        task_file = self._find_task_file(session_id)
        if not task_file or not task_file.exists():
            raise ValueError(f"Task file not found for session '{session_id}'")

        # Read existing content
        existing_content = task_file.read_text()
        
        # Extract title
        title_match = re.search(r"^#\s+(.+)$", existing_content, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else session_id

        # Build updated content
        # Keep the title and any content before the first ## heading
        title_section_match = re.search(r"(^#\s+.+$\n\n)", existing_content, re.MULTILINE)
        header = title_section_match.group(1) if title_section_match else f"# {title}\n\n"

        # Create updated content with fresh summary and conversation history
        updated_content = header
        updated_content += "## Summary\n"
        updated_content += f"{summary}\n\n"
        updated_content += "## Conversation History\n"
        updated_content += f"**User**: {user_message}\n\n"
        updated_content += f"**Assistant**: {assistant_response[:500]}{'...' if len(assistant_response) > 500 else ''}\n\n"
        
        # Keep any additional sections (Instructions, etc.)
        additional_sections = re.search(r"\n## Instructions\n[\s\S]*$", existing_content)
        if additional_sections:
            updated_content += additional_sections.group(0)

        # Write updated content
        task_file.write_text(updated_content)

        return {
            "success": True,
            "session_id": session_id,
            "task_file": str(task_file),
            "message": "Task summary updated successfully"
        }

    def get_session_summary(self, session_id: str) -> Optional[str]:
        """
        Get a summary for a specific session.

        Args:
            session_id: The session identifier

        Returns:
            Summary text if found, None otherwise
        """
        task_file = self._find_task_file(session_id)
        if task_file and task_file.exists():
            task_info = self._extract_task_summary(task_file)
            return task_info.get("summary", "")
        return None

    def get_all_sessions_with_summaries(self) -> list[dict]:
        """
        Get all sessions with their task summaries.

        Returns:
            List of dicts with session info including summary
        """
        if not self.assistant_file.exists():
            return []

        content = self.assistant_file.read_text()
        session_pattern = r"##\s+(.+?)\s*\n((?:-.*\n)*)"
        sessions = re.findall(session_pattern, content, re.MULTILINE)

        result = []
        for session_id, details in sessions:
            # Extract task file and title
            task_match = re.search(r"Task:\s*(.+?\.md)", details)
            title_match = re.search(r"Title:\s*(.+)", details)

            task_file = task_match.group(1).strip() if task_match else None
            title = title_match.group(1).strip() if title_match else session_id

            # Get summary from task file
            summary = None
            if task_file:
                task_path = Path(task_file)
                if task_path.exists():
                    task_info = self._extract_task_summary(task_path)
                    summary = task_info.get("summary", "")

            result.append({
                "session_id": session_id,
                "task_file": task_file,
                "title": title,
                "summary": summary
            })

        return result

    def delete_session(self, session_id: str) -> dict:
        """
        Delete a session entry from assistant.md and optionally its task file.

        Args:
            session_id: The session identifier to delete

        Returns:
            Dict with success status and details
        """
        if not self.assistant_file.exists():
            raise ValueError("Assistant file not found")

        content = self.assistant_file.read_text()
        
        # Find the session block and extract task file path
        session_pattern = rf"(##\s+{re.escape(session_id)}\s*\n(?:-.*\n)*)"
        session_block = re.search(session_pattern, content, re.MULTILINE)
        
        if not session_block:
            raise ValueError(f"Session '{session_id}' not found")

        # Extract task file path before removing
        task_match = re.search(r"Task:\s*(.+?\.md)", session_block.group(1))
        task_file = task_match.group(1).strip() if task_match else None

        # Remove the session block (including leading newlines)
        # Pattern matches the session header and all its detail lines
        full_pattern = rf"\n*##\s+{re.escape(session_id)}\s*\n(?:-.*\n)*"
        updated_content = re.sub(full_pattern, "", content, flags=re.MULTILINE)
        
        # Clean up multiple consecutive newlines
        updated_content = re.sub(r"\n{3,}", "\n\n", updated_content)

        # Write updated content back
        self.assistant_file.write_text(updated_content)

        # Delete task file if it exists
        task_deleted = False
        if task_file:
            task_path = Path(task_file)
            if task_path.exists():
                task_path.unlink()
                task_deleted = True

        return {
            "success": True,
            "session_id": session_id,
            "task_file": task_file,
            "task_deleted": task_deleted,
            "message": f"Session '{session_id}' deleted successfully"
        }

    def rename_session(self, session_id: str, new_title: str) -> dict:
        """
        Rename a session's display title and its associated task file.

        Args:
            session_id: The session identifier
            new_title: The new title for the session

        Returns:
            Dict with success status and details
        """
        if not self.assistant_file.exists():
            raise ValueError("Assistant file not found")

        content = self.assistant_file.read_text()
        
        # Find the session block
        session_pattern = rf"(##\s+{re.escape(session_id)}\s*\n((?:-.*\n)*))"
        match = re.search(session_pattern, content, re.MULTILINE)
        
        if not match:
            raise ValueError(f"Session '{session_id}' not found")

        full_block = match.group(1)
        details = match.group(2)
        
        # 1. Extract and rename task file
        task_match = re.search(r"Task:\s*(.+?\.md)", details)
        if not task_match:
             raise ValueError(f"No task file found for session '{session_id}'")
             
        old_task_file = Path(task_match.group(1).strip())
        
        # Create safe filename from new title
        safe_filename = new_title.lower().strip().replace(" ", "-").replace("_", "-")
        safe_filename = re.sub(r'[^a-z0-9\-]', '', safe_filename)
        if not safe_filename:
            safe_filename = "untitled-chat"
            
        new_task_filename = f"{safe_filename}.md"
        new_task_file = self.tasks_dir / new_task_filename
        
        # Handle filename collisions
        counter = 1
        base_filename = safe_filename
        while new_task_file.exists() and new_task_file != old_task_file:
            new_task_filename = f"{base_filename}-{counter}.md"
            new_task_file = self.tasks_dir / new_task_filename
            counter += 1
            
        old_task_path = self.assistant_file.parent / old_task_file if not old_task_file.is_absolute() else old_task_file
        new_task_path = self.tasks_dir / new_task_filename
        
        # Perform physical rename
        if old_task_path.exists():
            old_task_path.rename(new_task_path)
            
            # Update internal title if it's a markdown heading
            task_content = new_task_path.read_text()
            task_content = re.sub(r"^#\s+.*$", f"# {new_title}", task_content, count=1, flags=re.MULTILINE)
            new_task_path.write_text(task_content)

        # 2. Update assistant.md mapping
        # Update Task path and Title
        new_task_relative_path = os.path.relpath(new_task_path, self.assistant_file.parent)
        
        new_details = details
        new_details = re.sub(r"Task:\s*(.+?\.md)", f"Task: {new_task_relative_path}", new_details)
        
        if "Title:" in new_details:
            new_details = re.sub(r"Title:\s*(.*)", f"Title: {new_title}", new_details)
        else:
            new_details += f"- Title: {new_title}\n"
            
        updated_block = f"## {session_id}\n{new_details}"
        updated_content = content.replace(full_block, updated_block)
        self.assistant_file.write_text(updated_content)

        return {
            "success": True,
            "session_id": session_id,
            "new_title": new_title,
            "new_task_file": str(new_task_relative_path)
        }
