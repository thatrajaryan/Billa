import asyncio
import os
import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch
from app.chat.openrouter_chat import OpenRouterChat

async def test_checkpoint_standard():
    print("\n--- Testing Standard Stream Checkpointing ---")
    
    # Initialize
    project_root = Path("./test_env")
    if project_root.exists():
        shutil.rmtree(project_root)
    project_root.mkdir()
    (project_root / ".env").write_text("OPEN_ROUTER_API_KEY=test_key\nOPEN_ROUTER_MODEL=test_model\n")
    
    chat = OpenRouterChat(project_root=str(project_root))
    session_id = "test-session-std"
    
    # Mocking requests to simulate failure
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    
    def iter_lines_with_failure():
        yield b'data: {"choices": [{"delta": {"content": "Part 1 "}}]}'
        yield b'data: {"choices": [{"delta": {"content": "Part 2 "}}]}'
        raise RuntimeError("Network lost!")

    mock_response.iter_lines = iter_lines_with_failure

    print("Step 1: Sending message and simulating failure...")
    with patch('requests.post', return_value=mock_response):
        try:
            async for chunk in chat.send_message_stream("Tell me a story", session_id):
                print(f"Received: {chunk}")
        except Exception:
            pass # We expect an error handled by the generator yielding messages

    checkpoint_path = project_root / "checkpoints" / f"{session_id}.json"
    if checkpoint_path.exists():
        print("✅ Checkpoint created successfully.")
        with open(checkpoint_path) as f:
            data = json.load(f)
            print(f"Checkpoint data: {data}")
    else:
        print("❌ Checkpoint NOT created.")
        return

    print("\nStep 2: Resuming generation...")
    # Mock successful continuation
    mock_response_2 = MagicMock()
    mock_response_2.raise_for_status.return_value = None
    mock_response_2.iter_lines = lambda: [
        b'data: {"choices": [{"delta": {"content": "Part 3 "}}]}',
        b'data: {"choices": [{"delta": {"content": "Part 4"}}]}',
        b'data: [DONE]'
    ]

    with patch('requests.post', return_value=mock_response_2):
        async for chunk in chat.send_message_stream("continue", session_id):
            print(f"Received: {chunk}")

    if not checkpoint_path.exists():
        print("✅ Checkpoint cleared after successful completion.")
    else:
        print("❌ Checkpoint still exists.")

    shutil.rmtree(project_root)

async def test_checkpoint_research():
    print("\n--- Testing Research Loop Checkpointing ---")
    
    project_root = Path("./test_env_res")
    if project_root.exists():
        shutil.rmtree(project_root)
    project_root.mkdir()
    (project_root / ".env").write_text("OPEN_ROUTER_API_KEY=test_key\nOPEN_ROUTER_MODEL=test_model\n")
    (project_root / "SOUL.md").write_text("Soul rules")
    
    chat = OpenRouterChat(project_root=str(project_root))
    session_id = "test-session-res"
    
    # Mock stages
    chat._research_explore = MagicMock(return_value=asyncio.Future())
    chat._research_explore.return_value.set_result("Exploration data")
    
    async def mock_roadmap_fail(results):
        raise RuntimeError("Roadmap error!")
    
    chat._research_roadmap = mock_roadmap_fail

    print("Step 1: Starting research and simulating failure at Roadmap...")
    try:
        async for chunk in chat.send_message_stream("Research AI", session_id):
            print(f"UI Update: {chunk}")
    except Exception:
        pass

    checkpoint_path = project_root / "checkpoints" / f"{session_id}.json"
    if checkpoint_path.exists():
        print("✅ Research checkpoint created.")
        with open(checkpoint_path) as f:
            data = json.load(f)
            print(f"Stage reached: {data['stage']}")
    else:
        print("❌ Research checkpoint NOT created.")
        return

    print("\nStep 2: Resuming research loop...")
    # Now mock roadmap and writing to succeed
    chat._research_roadmap = MagicMock(return_value=asyncio.Future())
    chat._research_roadmap.return_value.set_result([{"title": "Ch1", "description": "Desc1"}])
    chat._research_write_chapter = MagicMock(return_value=asyncio.Future())
    chat._research_write_chapter.return_value.set_result("Chapter 1 content")
    chat._research_audit_chapter = MagicMock(return_value=asyncio.Future())
    chat._research_audit_chapter.return_value.set_result("Audit info")

    async for chunk in chat.send_message_stream("continue", session_id):
        if len(chunk) < 100:
            print(f"UI Update: {chunk}")
        else:
            print("UI Update: [Chapter content...]")

    if not checkpoint_path.exists():
        print("✅ Research checkpoint cleared after completion.")
    else:
        print("❌ Research checkpoint still exists.")

    shutil.rmtree(project_root)

if __name__ == "__main__":
    asyncio.run(test_checkpoint_standard())
    asyncio.run(test_checkpoint_research())
