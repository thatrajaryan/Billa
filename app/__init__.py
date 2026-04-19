import os
from pathlib import Path
from flask import Flask, render_template, request, jsonify, Response, stream_with_context, send_file, abort
import json
import asyncio
import threading
import queue
from concurrent.futures import ThreadPoolExecutor

from app.chat.base import Chat
from app.assistant import Assistant


def _run_async(coro):
    """Run an async coroutine in a synchronous context."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_app(chat_impl: Chat | None = None):
    """Create and configure the Flask application."""

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), "templates"),
        static_folder=os.path.join(os.path.dirname(__file__), "static")
    )

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")

    # Initialize assistant
    assistant = Assistant(os.path.join(os.path.dirname(__file__), "..", "assistant.md"))

    # Store chat implementation
    app.chat = chat_impl
    app.assistant = assistant
    
    # Thread pool for async operations
    executor = ThreadPoolExecutor(max_workers=4)

    @app.route("/")
    def index():
        """Render the main chat interface."""
        return render_template("index.html")

    @app.route("/api/chat", methods=["POST"])
    def chat():
        """Handle chat requests."""
        if not app.chat:
            return jsonify({"error": "Chat implementation not configured"}), 500

        data = request.get_json()
        message = data.get("message", "")
        session_id = data.get("session_id", "default")

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Get context from task.md
        context = app.assistant.get_task_context(session_id)

        try:
            # Run async function in thread pool
            future = executor.submit(
                _run_async,
                app.chat.send_message(message, session_id, context)
            )
            response = future.result(timeout=300)
            return jsonify({"response": response})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/chat/stream", methods=["POST"])
    def chat_stream():
        """Handle streaming chat requests."""
        if not app.chat:
            return jsonify({"error": "Chat implementation not configured"}), 500

        data = request.get_json()
        message = data.get("message", "")
        session_id = data.get("session_id", "default")

        if not message:
            return jsonify({"error": "Message is required"}), 400

        # Get context from task.md
        context = app.assistant.get_task_context(session_id)

        def generate():
            # Use a queue to communicate between threads
            q = queue.Queue()
            
            def stream_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    async def stream_gen():
                        try:
                            async for chunk in app.chat.send_message_stream(message, session_id, context):
                                q.put(f"data: {json.dumps({'chunk': chunk})}\n\n")
                            q.put(f"data: {json.dumps({'done': True})}\n\n")
                        except Exception as e:
                            q.put(f"data: {json.dumps({'error': str(e)})}\n\n")
                        finally:
                            q.put(None)  # Sentinel to signal completion

                    loop.run_until_complete(stream_gen())
                finally:
                    loop.close()

            # Start async stream in a separate thread
            thread = threading.Thread(target=stream_async)
            thread.start()

            try:
                while True:
                    chunk = q.get()
                    if chunk is None:
                        break
                    yield chunk
            finally:
                thread.join(timeout=5)

        return Response(
            stream_with_context(generate()),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no"
            }
        )

    @app.route("/api/sessions", methods=["GET"])
    def get_sessions():
        """Get all available chat sessions."""
        sessions = app.assistant.list_sessions()
        return jsonify({"sessions": sessions})

    @app.route("/api/tasks", methods=["GET"])
    def get_tasks():
        """Get all available task files with their summaries."""
        tasks = app.assistant.list_tasks()
        return jsonify({"tasks": tasks})

    @app.route("/api/sessions", methods=["POST"])
    def create_session():
        """Create a new session with an optional task."""
        data = request.get_json()
        session_id = data.get("session_id", "chat-" + str(len(app.assistant.list_sessions()) + 1))
        task_file = data.get("task_file", "tasks/default.md")
        title = data.get("title", session_id)
        
        # If using default task, create a new task file for this conversation
        if task_file == "tasks/default.md":
            # Create a new task file in tasks/ directory
            task_file = app.assistant.create_new_task(title)

        # Add session mapping
        app.assistant.add_session_mapping(session_id, task_file, title)

        return jsonify({
            "session_id": session_id,
            "task_file": task_file,
            "title": title
        }), 201

    @app.route("/api/sessions/<session_id>/task", methods=["GET"])
    def get_session_task(session_id):
        """Get the task context for a specific session."""
        context = app.assistant.get_task_context(session_id)
        if context:
            return jsonify({"context": context})
        return jsonify({"error": "Task context not found"}), 404

    @app.route("/api/sessions/detect", methods=["POST"])
    def detect_session():
        """Detect if a message matches an existing conversation."""
        data = request.get_json()
        message = data.get("message", "")

        if not message:
            return jsonify({"error": "Message is required"}), 400

        match = app.assistant.detect_matching_session(message)
        if match:
            return jsonify({"match": match})
        return jsonify({"match": None})

    @app.route("/api/sessions/with-summaries", methods=["GET"])
    def get_sessions_with_summaries():
        """Get all sessions with their task summaries."""
        sessions = app.assistant.get_all_sessions_with_summaries()
        return jsonify({"sessions": sessions})

    @app.route("/api/sessions/<session_id>/update-summary", methods=["POST"])
    def update_session_summary(session_id):
        """Update the task summary for a session after a conversation turn."""
        data = request.get_json()
        user_message = data.get("user_message", "")
        assistant_response = data.get("assistant_response", "")
        summary = data.get("summary", "")

        try:
            result = app.assistant.update_task_summary(session_id, user_message, assistant_response, summary)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/sessions/<session_id>", methods=["DELETE"])
    def delete_session(session_id):
        """Delete a session and optionally its associated task file."""
        try:
            result = app.assistant.delete_session(session_id)
            return jsonify(result), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/files", methods=["GET"])
    def list_files():
        """List all available files for download."""
        files_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "files"
        if not files_dir.exists():
            return jsonify({"files": []})

        files = []
        for file_path in files_dir.iterdir():
            if file_path.is_file():
                files.append({
                    "name": file_path.name,
                    "size": file_path.stat().st_size,
                    "path": str(file_path.relative_to(files_dir))
                })

        return jsonify({"files": files})

    @app.route("/api/files/<path:filename>", methods=["GET"])
    def download_file(filename):
        """Download a file from the files directory."""
        files_dir = Path(os.path.dirname(os.path.abspath(__file__))).parent / "files"
        file_path = files_dir / filename

        # Security check: prevent directory traversal
        if not file_path.exists() or not file_path.is_file():
            abort(404)

        if not str(file_path.resolve()).startswith(str(files_dir.resolve())):
            abort(403)

        return send_file(file_path, as_attachment=True)

    return app
