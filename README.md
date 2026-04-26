# 🧠 ChaturAI

ChaturAI is a powerful, agentic AI research assistant designed to go beyond simple chat. It implements advanced multi-stage reasoning protocols to deep-dive into complex topics, generate structured learning resources, and automatically manage project files.

## ✨ Features

### 🕵️ Agentic Research Protocol (ChaturAI)
When you ask ChaturAI to "research" or "learn" a topic, it initiates the **ChaturAI Protocol**, a multi-stage reasoning loop:
1.  **Deep Exploration**: Scours the topic for technical facts and core concepts.
2.  **Roadmap Creation**: Generates a structured, sequential learning path.
3.  **Iterative Writing**: Drafts comprehensive chapters with a focus on beginner-friendly explanations.
4.  **Supplemental Auditing**: Self-reviews content to explain complex terms and acronyms.
5.  **Auto-Consolidation**: Saves the entire research session to a downloadable Markdown file.
6.  **Auto-Naming**: Generates a title for the research session and automatically routes future sessions to it.

### 📁 Smart File Management
*   **Automatic Extraction**: ChaturAI detects code blocks in conversations and automatically saves them to the `files/` directory.
*   **Immersive File Viewer**: A full-page, high-performance binary-aware viewer for:
    *   **Code**: Syntax highlighting for Python, JS, CSS, and more.
    *   **Markdown**: Beautifully rendered compiled documents.
    *   **Text**: Clean, readable plain text.

### 🛡️ Resilience & Persistence
*   **Checkpoint Manager**: Automatically saves partial responses. If a stream is interrupted by a network failure, just type "continue" to pick up exactly where it left off. Handles clearance of unused checkpoints as a background task.
*   **User-Aware Interrupts**: Smart enough to clear state when you manually stop a session.

### 🔌 Multi-Model Support
*   **OpenRouter**: Access state-of-the-art models (Claude 3.5, GPT-4o, etc.).
*   **Local Qwen**: Deep integration with Qwen CLI for private, local processing.
*   **Ollama**: Seamless connection to your local Ollama instance.
*   To add support for any LLM provider, simply implement the `ModelProvider` interface and add it to the `app/chat/` directory.

---

## 🚀 Setting Up

### 1. Prerequisites
*   Python 3.9+
*   (Optional) [Ollama](https://ollama.com/) or [Qwen CLI](https://github.com/QwenLM/Qwen-7B) for local models.

### 2. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/rajaryan18/ChaturAI.git
cd ChaturAI
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the project root:
```env
OPEN_ROUTER_API_KEY=your_api_key_here
OPEN_ROUTER_MODEL=google/gemini-pro-1.5-exp  # Example model
```

### 4. Run the App
```bash
python3 run.py
```
The application will be live at `http://localhost:3000`.

---

## 🏗️ Architecture

ChaturAI uses a decoupled **Provider-Service** architecture:
*   **`ChatService`**: Handles the ChaturAI protocol, file saving, and checkpointing.
*   **`ModelProvider`**: Lightweight wrappers for different LLM backends.

```bash
├── app/
│   ├── chat/
│   │   ├── chat.py          # Central Business Logic (ChatService)
│   │   ├── base.py          # Interfaces
│   │   ├── openrouter.py    # Model Providers
│   │   ├── qwen.py
│   │   └── ollama.py
│   ├── static/              # Frontend Assets
│   └── templates/           # UI Layout
├── files/                   # Auto-saved output files
├── SOUL.md                  # Core personality and rules
└── run.py                   # Entry point
```

---

## 🎨 Philosophy (SOUL)
ChaturAI follows the rules defined in `SOUL.md`:
*   Always assume the user is a beginner.
*   Never leave technical terms unexplained.
*   Prioritize depth and technical accuracy over brevity.
