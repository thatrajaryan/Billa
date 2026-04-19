# AI Assistant

A Flask-based chat assistant application with a ChatGPT-like interface.

## Architecture

```
├── app/
│   ├── chat/
│   │   ├── base.py          # Abstract Chat class
│   │   └── example.py       # Example implementation
│   ├── templates/
│   │   └── index.html       # Main UI template
│   ├── static/
│   │   ├── css/style.css    # Styles
│   │   └── js/app.js        # Frontend logic
│   ├── __init__.py          # Flask app factory
│   └── assistant.py         # Session-task mapping manager
├── tasks/
│   ├── default.md           # Default task context
│   └── research-project.md  # Example task context
├── assistant.md             # Session to task mapping
├── run.py                   # Entry point
└── requirements.txt         # Dependencies
```

## How It Works

1. **Sessions & Context**: The `assistant.md` file maps chat sessions to their corresponding `task.md` files
2. **Chat Flow**: When a user sends a message, the assistant:
   - Looks up the session in `assistant.md`
   - Loads the associated `task.md` context
   - Passes the context to the Chat implementation
   - Returns the response with streaming support

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
python run.py
```

The app will be available at `http://localhost:5000`

## Creating a Custom Chat Implementation

1. Create a new file in `app/chat/` (e.g., `my_chat.py`)
2. Extend the `Chat` abstract class:

```python
from app.chat.base import Chat
from typing import AsyncGenerator

class MyChat(Chat):
    async def send_message(self, message: str, session_id: str, context: str | None = None) -> str:
        # Your implementation here
        pass

    async def send_message_stream(self, message: str, session_id: str, context: str | None = None) -> AsyncGenerator[str, None]:
        # Your streaming implementation here
        pass
```

3. Update `run.py` to use your implementation:

```python
from app.chat.my_chat import MyChat
chat_impl = MyChat()
app = create_app(chat_impl)
```

## Adding New Sessions

Edit `assistant.md` to add new session mappings:

```markdown
## my-new-session
- Task: tasks/my-new-session.md
```

Then create the corresponding `task.md` file in the `tasks/` directory.

## Features

- 💬 ChatGPT-like interface
- 🔄 Streaming responses
- 📁 Session-based context loading
- 🎨 Dark theme
- 📱 Responsive design
- 🔌 Pluggable chat implementations
