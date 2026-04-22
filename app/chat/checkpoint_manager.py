import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

class CheckpointManager:
    """Manages session checkpoints for persistent chat states."""

    def __init__(self, checkpoints_dir: str = "checkpoints"):
        self.checkpoints_dir = Path(checkpoints_dir)
        self._ensure_dir_exists()

    def _ensure_dir_exists(self):
        """Ensure the checkpoints directory exists."""
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)

    def _get_checkpoint_path(self, session_id: str) -> Path:
        """Get the file path for a session checkpoint."""
        return self.checkpoints_dir / f"{session_id}.json"

    def save_checkpoint(self, session_id: str, data: Dict[str, Any]):
        """Save session data to a checkpoint file."""
        checkpoint_path = self._get_checkpoint_path(session_id)
        try:
            with open(checkpoint_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"[CheckpointManager] Saved checkpoint for session: {session_id}")
        except Exception as e:
            print(f"[CheckpointManager] Failed to save checkpoint for {session_id}: {e}")

    def load_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Load session data from a checkpoint file."""
        checkpoint_path = self._get_checkpoint_path(session_id)
        if not checkpoint_path.exists():
            return None
        
        try:
            with open(checkpoint_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[CheckpointManager] Failed to load checkpoint for {session_id}: {e}")
            return None

    def clear_checkpoint(self, session_id: str):
        """Delete a checkpoint file after successful completion or manual reset."""
        checkpoint_path = self._get_checkpoint_path(session_id)
        if checkpoint_path.exists():
            try:
                checkpoint_path.unlink()
                print(f"[CheckpointManager] Cleared checkpoint for session: {session_id}")
            except Exception as e:
                print(f"[CheckpointManager] Failed to clear checkpoint for {session_id}: {e}")

    def exists(self, session_id: str) -> bool:
        """Check if a checkpoint exists for a session."""
        return self._get_checkpoint_path(session_id).exists()
