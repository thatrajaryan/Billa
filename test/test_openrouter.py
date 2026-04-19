import asyncio
import os
from app.chat.openrouter_chat import OpenRouterChat

async def test_openrouter():
    print("--- Testing OpenRouterChat ---")
    
    # Initialize
    try:
        chat = OpenRouterChat(project_root=".")
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

    print(f"\n[Test 2] Sending message (streaming): {message}")
    try:
        print("Response: ", end="", flush=True)
        async for chunk in chat.send_message_stream(message, session_id):
            print(chunk, end="", flush=True)
        print("\nStream completed.")
    except Exception as e:
        print(f"\nTest 2 failed: {e}")

    print(f"\n[Test 3] Testing file extraction")
    file_extraction_msg = "Create a file named 'hello_test.txt' with the content 'Hello from OpenRouter!'. Format it as: hello_test.txt\\n```text\\nHello from OpenRouter!\\n```"
    try:
        response = await chat.send_message(file_extraction_msg, session_id)
        print(f"Response received. Checking if 'files/hello_test.txt' exists...")
        if os.path.exists("files/hello_test.txt"):
            content = open("files/hello_test.txt").read()
            print(f"File exists! Content: {content}")
        else:
            print("File DOES NOT exist.")
    except Exception as e:
        print(f"Test 3 failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_openrouter())
