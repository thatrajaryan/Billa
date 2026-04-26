import os
from app import create_app
from app.chat.chat import ChatService
from app.chat.openrouter import OpenRouterModel
from dotenv import load_dotenv


# Create the app with OpenRouter model and ChatService
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))

assistant_file = os.path.join(project_root, "assistant.md")

# New Architecture: Provider + Service
model = OpenRouterModel()
chat_impl = ChatService(provider=model, project_root=project_root, assistant_file=assistant_file)
app = create_app(chat_impl)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(debug=True, host="0.0.0.0", port=port)
