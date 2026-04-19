import os
from app import create_app
from app.chat.openrouter_chat import OpenRouterChat


# Create the app with OpenRouter chat implementation
project_root = os.path.dirname(os.path.abspath(__file__))
assistant_file = os.path.join(project_root, "assistant.md")
chat_impl = OpenRouterChat(project_root=project_root, assistant_file=assistant_file)
app = create_app(chat_impl)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, host="0.0.0.0", port=port)
