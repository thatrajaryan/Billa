import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from app.chat.openrouter_chat import OpenRouterChat

class MockResponse:
    def __init__(self, json_data):
        self.json_data = json_data
    def json(self):
        return self.json_data
    def raise_for_status(self):
        pass

class TestResearchLoop(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Create a temporary SOUL.md if needed
        self.project_root = Path("./test_root")
        self.project_root.mkdir(exist_ok=True)
        (self.project_root / "SOUL.md").write_text("# Mock SOUL")
        
        # Patch environment variables
        with patch.dict('os.environ', {
            'OPEN_ROUTER_API_KEY': 'mock_key',
            'OPEN_ROUTER_MODEL': 'mock_model'
        }):
            self.chat = OpenRouterChat(project_root=str(self.project_root))

    def tearDown(self):
        # Cleanup
        import shutil
        if self.project_root.exists():
            shutil.rmtree(self.project_root)

    @patch('requests.post')
    async def test_research_loop_flow(self, mock_post):
        # Setup mock responses for each stage
        explore_data = {"choices": [{"message": {"content": "Exploration findings."}}]}
        roadmap_data = {"choices": [{"message": {"content": '[{"title": "Intro", "description": "Desc"}]'}}]}
        write_data = {"choices": [{"message": {"content": "Chapter 1 content."}}]}
        audit_data = {"choices": [{"message": {"content": "Audit additions."}}]}
        
        mock_post.side_effect = [
            MockResponse(explore_data),
            MockResponse(roadmap_data),
            MockResponse(write_data),
            MockResponse(audit_data)
        ]

        chunks = []
        async for chunk in self.chat.send_message_stream("Explain AI", "test_session"):
            chunks.append(chunk)

        # Verify chunks contain progress markers
        full_text = "".join(chunks)
        self.assertIn("ChaturAI Research Protocol: Initiated", full_text)
        self.assertIn("Gathering initial information", full_text)
        self.assertIn("Created 1 chapters", full_text)
        self.assertIn("Processing Chapter 1", full_text)
        self.assertIn("Chapter 1 content", full_text)
        self.assertIn("Audit additions", full_text)
        self.assertIn("Research Complete", full_text)

        # Verify file was saved
        saved_files = list((self.project_root / "files").glob("research_test_session_*.md"))
        self.assertEqual(len(saved_files), 1)
        content = saved_files[0].read_text()
        self.assertIn("# Research: Explain AI", content)
        self.assertIn("Exploration findings", content)
        self.assertIn("Chapter 1 content", content)
        self.assertIn("Audit additions", content)

if __name__ == "__main__":
    unittest.main()
