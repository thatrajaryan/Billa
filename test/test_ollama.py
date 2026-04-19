import asyncio
import os
from app.chat.ollama_chat import OllamaChat

async def test_ollama():
    print("--- Testing OllamaChat ---")
    
    # Initialize
    try:
        chat = OllamaChat(project_root=".")
        print(f"Initialized with model: {chat.model}")
    except Exception as e:
        print(f"Initialization failed: {e}")
        return

    session_id = "test-session"
    message = "Hello, who are you? Please reply in one sentence."
    
    print(f"\n[Test 1] Sending message (non-streaming): {message}")
    try:
        response = await chat.send_message(message, session_id)
        print(f"Response: {response}")
    except Exception as e:
        print(f"Test 1 failed: {e}")
        print("Note: Make sure Ollama is running locally at http://localhost:11434")

    print(f"\n[Test 2] Sending message (streaming): {message}")
    try:
        print("Response: ", end="", flush=True)
        async for chunk in chat.send_message_stream(message, session_id):
            print(chunk, end="", flush=True)
        print("\nStream completed.")
    except Exception as e:
        print(f"\nTest 2 failed: {e}")

    print(f"\n[Test 3] Testing file extraction")
    file_extraction_msg = "Create a file named 'hello_ollama.txt' with the content 'Hello from Ollama!'. Format it as: hello_ollama.txt\\n```text\\nHello from Ollama!\\n```"
    try:
        response = await chat.send_message(file_extraction_msg, session_id)
        print(f"Response received. Checking if 'files/hello_ollama.txt' exists...")
        if os.path.exists("files/hello_ollama.txt"):
            content = open("files/hello_ollama.txt").read()
            print(f"File exists! Content: {content}")
        else:
            print("File DOES NOT exist.")
    except Exception as e:
        print(f"Test 3 failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_ollama())
