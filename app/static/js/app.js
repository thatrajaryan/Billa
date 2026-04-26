// State
let currentSessionId = "assistant";
let currentTaskFile = "tasks/default.md";
let isWaitingForResponse = false;
let sessions = [];
let tasks = [];
let pendingDeleteSession = null;
let isFirstMessage = true;
let currentAbortController = null;

// DOM Elements
const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const welcomeMessage = document.getElementById("welcome-message");
const sendBtn = document.getElementById("send-btn");
const newChatBtn = document.getElementById("new-chat-btn");
const sessionsList = document.getElementById("sessions-list");
const sessionTitle = document.getElementById("session-title");
const modal = document.getElementById("conversation-modal");
const closeModal = document.getElementById("close-modal");
const existingConversations = document.getElementById("existing-conversations");
const taskOptions = document.getElementById("task-options");
const deleteModal = document.getElementById("delete-modal");
const closeDeleteModal = document.getElementById("close-delete-modal");
const deleteSessionName = document.getElementById("delete-session-name");
const confirmDeleteBtn = document.getElementById("confirm-delete-btn");
const cancelDeleteBtn = document.getElementById("cancel-delete-btn");
const filesBtn = document.getElementById("files-btn");
const filesModal = document.getElementById("files-modal");
const closeFilesModal = document.getElementById("close-files-modal");
const filesList = document.getElementById("files-list");
const fullPageViewer = document.getElementById("full-page-viewer");
const closeViewerBtn = document.getElementById("close-viewer-btn");
const viewerTitle = document.getElementById("viewer-title");
const viewerContent = document.getElementById("file-content");
const viewerDownload = document.getElementById("viewer-download");

// Initialize
document.addEventListener("DOMContentLoaded", () => {
    loadSessions();
    loadTasks();
    setupEventListeners();

    // Set ChaturAI Home as active by default
    sessionTitle.textContent = "ChaturAI Home";
});

function setupEventListeners() {
    chatForm.addEventListener("submit", handleSendMessage);

    messageInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            chatForm.requestSubmit();
        }
    });

    messageInput.addEventListener("input", autoResizeTextarea);

    newChatBtn.addEventListener("click", () => {
        // Create a new default session
        const sessionId = "chat-" + Date.now();
        currentSessionId = sessionId;
        currentTaskFile = "tasks/default.md";
        sessionTitle.textContent = "New Chat";
        chatMessages.innerHTML = "";
        showWelcomeMessage();

        // Register the session
        fetch("/api/sessions", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                session_id: sessionId,
                task_file: "tasks/default.md",
                title: "New Chat"
            }),
        }).then(() => loadSessions());

        highlightActiveSession();
    });

    closeModal.addEventListener("click", () => hideConversationModal());

    // Close modal when clicking outside
    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            hideConversationModal();
        }
    });

    // Delete modal event listeners
    closeDeleteModal.addEventListener("click", () => hideDeleteModal());

    cancelDeleteBtn.addEventListener("click", () => hideDeleteModal());

    confirmDeleteBtn.addEventListener("click", async () => {
        if (pendingDeleteSession) {
            await deleteSession(pendingDeleteSession);
            hideDeleteModal();
        }
    });

    deleteModal.addEventListener("click", (e) => {
        if (e.target === deleteModal) {
            hideDeleteModal();
        }
    });

    // Files modal event listeners
    filesBtn.addEventListener("click", () => showFilesModal());

    closeFilesModal.addEventListener("click", () => hideFilesModal());

    filesModal.addEventListener("click", (e) => {
        if (e.target === filesModal) {
            hideFilesModal();
        }
    });

    // Viewer event listeners
    closeViewerBtn.addEventListener("click", () => hideViewerModal());
}

function autoResizeTextarea() {
    messageInput.style.height = "auto";
    messageInput.style.height = Math.min(messageInput.scrollHeight, 200) + "px";
}

async function loadSessions() {
    try {
        const response = await fetch("/api/sessions/with-summaries");
        const data = await response.json();
        sessions = data.sessions;
        renderSessions(data.sessions);
    } catch (error) {
        console.error("Failed to load sessions:", error);
    }
}

async function loadTasks() {
    try {
        const response = await fetch("/api/tasks");
        const data = await response.json();
        tasks = data.tasks;
    } catch (error) {
        console.error("Failed to load tasks:", error);
    }
}

function showConversationModal() {
    loadTasks().then(() => {
        renderExistingConversations();
        renderTaskOptions();
        modal.style.display = "flex";
    });
}

function hideConversationModal() {
    modal.style.display = "none";
}

function showDeleteConfirmation(session, displayName) {
    pendingDeleteSession = session;
    deleteSessionName.textContent = displayName;
    deleteModal.style.display = "flex";
}

function hideDeleteModal() {
    deleteModal.style.display = "none";
    pendingDeleteSession = null;
}

async function deleteSession(session) {
    try {
        const response = await fetch(`/api/sessions/${session.session_id}`, {
            method: "DELETE",
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || "Failed to delete session");
        }

        // If we're currently viewing this session, switch to Assistant
        if (currentSessionId === session.session_id) {
            switchToAssistant();
        }

        // Reload sessions
        loadSessions();

    } catch (error) {
        console.error("Failed to delete session:", error);
        alert(`Failed to delete conversation: ${error.message}`);
    }
}

function showFilesModal() {
    loadFiles();
    filesModal.style.display = "flex";
}

function hideFilesModal() {
    filesModal.style.display = "none";
}

async function loadFiles() {
    try {
        const response = await fetch("/api/files");
        const data = await response.json();
        renderFiles(data.files);
    } catch (error) {
        console.error("Failed to load files:", error);
        filesList.innerHTML = '<p style="color: var(--text-secondary);">Failed to load files</p>';
    }
}

function renderFiles(files) {
    filesList.innerHTML = "";

    if (files.length === 0) {
        filesList.innerHTML = '<p style="color: var(--text-secondary); text-align: center; padding: 24px;">No files created yet. Ask ChaturAI to create a file!</p>';
        return;
    }

    files.forEach(file => {
        const fileEl = document.createElement("div");
        fileEl.className = "file-item";

        const size = file.size < 1024 ? `${file.size} B` :
            file.size < 1024 * 1024 ? `${(file.size / 1024).toFixed(1)} KB` :
                `${(file.size / (1024 * 1024)).toFixed(1)} MB`;

        fileEl.innerHTML = `
            <div class="file-info">
                <div class="file-name">${file.name}</div>
                <div class="file-size">${size}</div>
            </div>
            <div class="file-actions">
                <button class="view-btn" onclick="viewFile('${file.path}')">👁 View</button>
                <a href="/api/files/${file.path}" download class="download-btn" title="Download">
                    ⬇ Download
                </a>
            </div>
        `;
        filesList.appendChild(fileEl);
    });
}

function hideViewerModal() {
    fullPageViewer.style.display = "none";
    viewerContent.innerHTML = "";
    document.body.style.overflow = "auto";
}

window.viewFile = async function (path) {
    try {
        viewerTitle.textContent = "Loading...";
        fullPageViewer.style.display = "flex";
        document.body.style.overflow = "hidden";

        const response = await fetch(`/api/files/content/${path}`);
        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.error || "Failed to load file content");
        }

        const file = await response.json();
        viewerTitle.textContent = file.name;
        viewerDownload.href = `/api/files/${path}`;

        const ext = file.extension;

        if (ext === '.md') {
            // Render Markdown
            viewerContent.className = "file-content-container markdown-viewer";
            viewerContent.innerHTML = marked.parse(file.content);
            // Highlight any code blocks within the markdown
            viewerContent.querySelectorAll('pre code').forEach((block) => {
                hljs.highlightElement(block);
            });
        } else if (['.py', '.js', '.css', '.html', '.json', '.sh', '.yaml', '.yml'].includes(ext)) {
            // Render Code with Syntax Highlighting
            viewerContent.className = "file-content-container code-viewer";
            const codeEl = document.createElement('pre');
            const innerCode = document.createElement('code');
            innerCode.textContent = file.content;

            // Map extensions to hljs languages if needed
            let lang = ext.slice(1);
            if (lang === 'py') lang = 'python';
            innerCode.className = `language-${lang}`;

            codeEl.appendChild(innerCode);
            viewerContent.appendChild(codeEl);
            hljs.highlightElement(innerCode);
        } else {
            // Plain text
            viewerContent.className = "file-content-container text-viewer";
            const pre = document.createElement('pre');
            pre.textContent = file.content;
            pre.style.whiteSpace = "pre-wrap";
            viewerContent.appendChild(pre);
        }

    } catch (error) {
        console.error("Failed to view file:", error);
        viewerTitle.textContent = "Error";
        viewerContent.innerHTML = `<p style="color: #ef4444;">${error.message}</p>`;
    }
}

function renderExistingConversations() {
    existingConversations.innerHTML = "";

    if (sessions.length === 0) {
        existingConversations.innerHTML = '<p style="color: var(--text-secondary); font-size: 14px;">No existing conversations</p>';
        return;
    }

    sessions.forEach(session => {
        const item = document.createElement("div");
        item.className = "conversation-item";

        // Use task filename as the title
        const taskName = session.task_file
            ? session.task_file.split('/').pop().replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
            : session.session_id;
        const displayName = taskName.charAt(0).toUpperCase() + taskName.slice(1);

        item.innerHTML = `
            <div class="conversation-item-header">
                <div class="conversation-item-title">${displayName}</div>
            </div>
            ${session.summary ? `<div class="conversation-item-summary">${session.summary}</div>` : ""}
        `;
        item.addEventListener("click", () => {
            continueConversation(session.session_id);
            hideConversationModal();
        });
        existingConversations.appendChild(item);
    });
}

function renderTaskOptions() {
    taskOptions.innerHTML = "";

    tasks.forEach(task => {
        const option = document.createElement("div");
        option.className = "task-option";
        option.innerHTML = `
            <div class="task-option-name">${task.name}</div>
            ${task.summary ? `<div class="task-option-summary">${task.summary}</div>` : ""}
        `;
        option.addEventListener("click", () => {
            createNewConversationWithTask(task);
        });
        taskOptions.appendChild(option);
    });
}

async function continueConversation(sessionId) {
    currentSessionId = sessionId;

    // Clear chat and show welcome before loading context
    chatMessages.innerHTML = "";
    showWelcomeMessage();

    // Find the session object
    const session = sessions.find(s => s.session_id === sessionId);

    // Load task context for this session
    try {
        const response = await fetch(`/api/sessions/${sessionId}/task`);
        const data = await response.json();
        if (data.context) {
            currentTaskFile = data.context;
            showTaskContext(data.context);
        }
    } catch (error) {
        console.error("Failed to load task context:", error);
    }

    // Update title from task filename
    const taskName = session && session.task_file
        ? session.task_file.split('/').pop().replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
        : sessionId;
    sessionTitle.textContent = taskName.charAt(0).toUpperCase() + taskName.slice(1);

    // Update active state
    highlightActiveSession();
}

function extractTaskInfo(taskContent) {
    // Extract title
    const titleMatch = taskContent.match(/^#\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1] : "Untitled";

    // Extract summary
    const summaryMatch = taskContent.match(/## Summary\n([\s\S]*?)(?=\n##|$)/);
    const summary = summaryMatch ? summaryMatch[1].trim() : "";

    return { title, summary };
}

function showTaskContext(markdown) {
    const headerEl = document.createElement("div");
    headerEl.className = "task-context-header";

    // Extract title from first # heading
    const titleMatch = markdown.match(/^#\s+(.+)$/m);
    const title = titleMatch ? titleMatch[1] : "Task Context";

    // Remove the title from body if it's there
    let bodyMarkdown = markdown;
    if (titleMatch) {
        bodyMarkdown = markdown.replace(titleMatch[0], "").trim();
    }

    headerEl.innerHTML = `
        <div class="task-context-label">Current Task Context</div>
        <div class="task-context-title">${title}</div>
        <div class="task-context-body" id="task-context-body">
            ${formatMessage(bodyMarkdown)}
        </div>
        <div class="task-context-footer">
            <button class="task-context-toggle" id="task-context-toggle">Collapse Context</button>
        </div>
    `;

    chatMessages.prepend(headerEl);

    const toggleBtn = headerEl.querySelector("#task-context-toggle");
    const bodyEl = headerEl.querySelector("#task-context-body");

    toggleBtn.addEventListener("click", () => {
        const isCollapsed = bodyEl.style.display === "none";
        bodyEl.style.display = isCollapsed ? "block" : "none";
        toggleBtn.textContent = isCollapsed ? "Collapse Context" : "Show Task Context";
    });
}

async function createNewConversationWithTask(task) {
    const sessionId = "chat-" + Date.now();
    currentSessionId = sessionId;
    currentTaskFile = task.path;

    // Create session mapping
    try {
        await fetch("/api/sessions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                session_id: sessionId,
                task_file: task.path,
                title: task.name
            }),
        });
    } catch (error) {
        console.error("Failed to create session:", error);
    }

    sessionTitle.textContent = task.name;
    chatMessages.innerHTML = "";
    showWelcomeMessage();

    // Reload sessions to include the new one
    loadSessions();

    // Update active state
    highlightActiveSession();

    // Hide the modal
    hideConversationModal();
}

function renderSessions(sessions) {
    sessionsList.innerHTML = "";

    // Always show "Assistant" as the first option
    const assistantEl = document.createElement("div");
    assistantEl.className = "session-item";
    assistantEl.textContent = "Assistant";
    assistantEl.addEventListener("click", () => {
        switchToAssistant();
    });
    sessionsList.appendChild(assistantEl);

    if (sessions.length === 0) {
        // No additional sessions yet
        return;
    }

    sessions.forEach(session => {
        const sessionEl = document.createElement("div");
        sessionEl.className = "session-item";

        // Use task name (from filename) as the title
        const taskName = session.task_file
            ? session.task_file.split('/').pop().replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
            : session.session_id;
        const displayName = taskName.charAt(0).toUpperCase() + taskName.slice(1);

        // Create text span for the session name
        const nameSpan = document.createElement("span");
        nameSpan.className = "session-name";
        nameSpan.textContent = displayName;
        sessionEl.appendChild(nameSpan);

        // Create delete button
        const deleteBtn = document.createElement("button");
        deleteBtn.className = "session-delete-btn";
        deleteBtn.innerHTML = "×";
        deleteBtn.title = "Delete conversation";
        deleteBtn.addEventListener("click", (e) => {
            e.stopPropagation();
            showDeleteConfirmation(session, displayName);
        });
        sessionEl.appendChild(deleteBtn);

        // Click to switch to conversation
        sessionEl.addEventListener("click", () => {
            continueConversation(session.session_id);
        });

        sessionsList.appendChild(sessionEl);
    });
}

function switchToAssistant() {
    currentSessionId = "assistant";
    sessionTitle.textContent = "ChaturAI Home";
    chatMessages.innerHTML = "";
    showWelcomeMessage();
    isFirstMessage = true;

    // Update active state - Assistant is always first
    highlightActiveSession();
}

function highlightActiveSession() {
    document.querySelectorAll(".session-item").forEach((el, index) => {
        if (currentSessionId === "assistant") {
            el.classList.toggle("active", index === 0);
        } else {
            // Find the session with matching session_id
            const session = sessions.find(s => s.session_id === currentSessionId);
            if (session) {
                const taskName = session.task_file
                    ? session.task_file.split('/').pop().replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
                    : session.session_id;
                const displayName = taskName.charAt(0).toUpperCase() + taskName.slice(1);
                el.classList.toggle("active", el.textContent === displayName);
            }
        }
    });
}

function showWelcomeMessage() {
    welcomeMessage.style.display = "flex";
}

function hideWelcomeMessage() {
    welcomeMessage.style.display = "none";
}

function addMessage(role, content) {
    hideWelcomeMessage();

    const messageEl = document.createElement("div");
    messageEl.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "U" : "A";

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";
    contentEl.innerHTML = formatMessage(content);

    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);

    chatMessages.appendChild(messageEl);
    scrollToBottom();

    return messageEl;
}

function addStreamingMessage(role) {
    hideWelcomeMessage();

    const messageEl = document.createElement("div");
    messageEl.className = `message ${role}`;

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = role === "user" ? "U" : "A";

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";

    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);
    chatMessages.appendChild(messageEl);

    return contentEl;
}

function addTypingIndicator() {
    hideWelcomeMessage();

    const messageEl = document.createElement("div");
    messageEl.className = "message assistant";
    messageEl.id = "typing-indicator";

    const avatar = document.createElement("div");
    avatar.className = "message-avatar";
    avatar.textContent = "A";

    const contentEl = document.createElement("div");
    contentEl.className = "message-content";
    contentEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';

    messageEl.appendChild(avatar);
    messageEl.appendChild(contentEl);
    chatMessages.appendChild(messageEl);
    scrollToBottom();
}

function removeTypingIndicator() {
    const indicator = document.getElementById("typing-indicator");
    if (indicator) {
        indicator.remove();
    }
}

function formatMessage(text) {
    // Handle markdown code blocks
    let formatted = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");

    // Handle fenced code blocks with optional language
    formatted = formatted.replace(/```(\w*)\n([\s\S]*?)```/g, function (match, lang, code) {
        const language = lang || 'code';
        return `<pre class="code-block"><div class="code-header">${language}<button class="copy-btn" onclick="copyCode(this)">Copy</button></div><code>${code.trim()}</code></pre>`;
    });

    // Handle inline code
    formatted = formatted.replace(/`([^`]+)`/g, "<code class='inline-code'>$1</code>");

    // Handle headers
    formatted = formatted.replace(/^### (.+)$/gm, "<h3>$1</h3>");
    formatted = formatted.replace(/^## (.+)$/gm, "<h2>$1</h2>");
    formatted = formatted.replace(/^# (.+)$/gm, "<h1>$1</h1>");

    // Handle bold
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    formatted = formatted.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

    // Handle italic
    formatted = formatted.replace(/\*(.+?)\*/g, "<em>$1</em>");
    formatted = formatted.replace(/_(.+?)_/g, "<em>$1</em>");

    // Handle lists
    formatted = formatted.replace(/^\- (.+)$/gm, "<li>$1</li>");
    formatted = formatted.replace(/^(\d+)\. (.+)$/gm, "<li>$2</li>");

    // Wrap consecutive li elements in ul
    formatted = formatted.replace(/(<li>.*<\/li>\n?)+/g, function (match) {
        return "<ul>" + match + "</ul>";
    });

    // Handle line breaks
    formatted = formatted.replace(/\n/g, "<br>");

    // Clean up extra breaks after block elements
    formatted = formatted.replace(/(<\/pre>|<\/h[1-3]>|<\/ul>)<br>/g, "$1");

    return formatted;
}

// Global function for copy button
window.copyCode = function (btn) {
    const codeBlock = btn.closest('.code-block').querySelector('code');
    const text = codeBlock.textContent;
    navigator.clipboard.writeText(text).then(() => {
        btn.textContent = 'Copied!';
        setTimeout(() => {
            btn.textContent = 'Copy';
        }, 2000);
    });
}

function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function handleSendMessage(e) {
    e.preventDefault();

    const message = messageInput.value.trim();

    // If already waiting for response, the button acts as a stop button
    if (isWaitingForResponse) {
        if (currentAbortController) {
            currentAbortController.abort();
            currentAbortController = null;
        }
        return;
    }

    if (!message) return;

    // If we're in ChaturAI Home, try to detect matching conversation
    if (currentSessionId === "assistant") {
        const match = await detectMatchingConversation(message);
        if (match) {
            // Auto-route to existing conversation
            await routeToConversation(message, match.session_id);
            return;
        } else {
            // Auto-create new conversation with task file
            await createAndRouteToNewConversation(message);
            return;
        }
    }

    // Add user message
    addMessage("user", message);

    // Clear input
    messageInput.value = "";
    messageInput.style.height = "auto";

    // Show typing indicator and switch to stop button
    isWaitingForResponse = true;
    updateSendButtonState("stop");
    addTypingIndicator();

    try {
        // Use streaming response
        const response = await sendStreamingMessage(message);

        // After first message in a non-assistant session, rename it
        if (isFirstMessage && currentSessionId !== "assistant") {
            try {
                const renameResponse = await fetch(`/api/sessions/${currentSessionId}/rename`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ prompt: message })
                });
                const renameData = await renameResponse.json();
                if (renameData.success) {
                    sessionTitle.textContent = renameData.new_title;
                    loadSessions();
                }
            } catch (error) {
                console.error("Failed to rename session:", error);
            }
        }

        // After receiving response, update task file with summary
        if (currentSessionId !== "assistant") {
            await updateTaskSummary(currentSessionId, message, response);
        }
    } catch (error) {
        console.error("Error sending message:", error);
        addMessage("assistant", "Sorry, an error occurred. Please try again.");
    } finally {
        removeTypingIndicator();
        isWaitingForResponse = false;
        updateSendButtonState("send");
        sendBtn.disabled = false;
        isFirstMessage = false;
    }
}

async function detectMatchingConversation(message) {
    try {
        const response = await fetch("/api/sessions/detect", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ message: message }),
        });

        const data = await response.json();
        return data.match;
    } catch (error) {
        console.error("Failed to detect matching conversation:", error);
        return null;
    }
}

async function routeToConversation(message, sessionId) {
    // Route to an existing conversation and send the message directly
    currentSessionId = sessionId;

    // Find the session object
    const session = sessions.find(s => s.session_id === sessionId);

    // Clear chat and show welcome before loading context
    chatMessages.innerHTML = "";
    showWelcomeMessage();

    // Load task context for this session
    try {
        const response = await fetch(`/api/sessions/${sessionId}/task`);
        const data = await response.json();
        if (data.context) {
            currentTaskFile = data.context;
            showTaskContext(data.context);
        }
    } catch (error) {
        console.error("Failed to load task context:", error);
    }

    // Update title from task filename
    const taskName = session && session.task_file
        ? session.task_file.split('/').pop().replace('.md', '').replace(/-/g, ' ').replace(/_/g, ' ')
        : sessionId;
    sessionTitle.textContent = taskName.charAt(0).toUpperCase() + taskName.slice(1);

    // Update active state
    highlightActiveSession();

    // Now send the message directly to this conversation
    addMessage("user", message);
    messageInput.value = "";
    messageInput.style.height = "auto";

    isWaitingForResponse = true;
    updateSendButtonState("stop");
    addTypingIndicator();

    try {
        await sendStreamingMessage(message);
    } catch (error) {
        console.error("Error sending message:", error);
        addMessage("assistant", "Sorry, an error occurred. Please try again.");
    } finally {
        removeTypingIndicator();
        isWaitingForResponse = false;
        updateSendButtonState("send");
        sendBtn.disabled = false;
    }
}

async function createAndRouteToNewConversation(message) {
    // Create a new conversation and send the message directly
    const sessionId = "chat-" + Date.now();
    currentSessionId = sessionId;
    currentTaskFile = "tasks/default.md";
    isFirstMessage = true;

    // Create session mapping with first message as title context
    try {
        await fetch("/api/sessions", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                session_id: sessionId,
                task_file: "tasks/default.md",
                title: message.substring(0, 50)
            }),
        });
    } catch (error) {
        console.error("Failed to create session:", error);
    }

    sessionTitle.textContent = message.substring(0, 50);
    chatMessages.innerHTML = "";
    showWelcomeMessage();

    // Reload sessions to include the new one
    loadSessions();

    // Update active state
    highlightActiveSession();

    // Now send the message directly to this new conversation
    addMessage("user", message);
    messageInput.value = "";
    messageInput.style.height = "auto";

    isWaitingForResponse = true;
    updateSendButtonState("stop");
    addTypingIndicator();

    try {
        await sendStreamingMessage(message);
    } catch (error) {
        console.error("Error sending message:", error);
        addMessage("assistant", "Sorry, an error occurred. Please try again.");
    } finally {
        removeTypingIndicator();
        isWaitingForResponse = false;
        updateSendButtonState("send");
        sendBtn.disabled = false;
    }
}

async function sendStreamingMessage(message) {
    currentAbortController = new AbortController();
    const signal = currentAbortController.signal;

    const response = await fetch("/api/chat/stream", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message: message,
            session_id: currentSessionId,
        }),
        signal: signal
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error || "Request failed");
    }

    const contentEl = addStreamingMessage("assistant");
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullMessage = "";

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const text = decoder.decode(value);
            const lines = text.split("\n");

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const data = JSON.parse(line.slice(6));

                    if (data.chunk) {
                        fullMessage += data.chunk;
                        contentEl.innerHTML = formatMessage(fullMessage);
                        scrollToBottom();
                    }

                    if (data.error) {
                        throw new Error(data.error);
                    }
                }
            }
        }
    } catch (error) {
        if (error.name === 'AbortError') {
            contentEl.innerHTML += `<br><span style="color: #f59e0b;">[Stream stopped by user]</span>`;
        } else if (!fullMessage) {
            throw error;
        } else {
            contentEl.innerHTML += `<br><span style="color: #ef4444;">[Stream interrupted]</span>`;
        }
    } finally {
        currentAbortController = null;
    }

    return fullMessage;
}

async function updateSendButtonState(state) {
    if (state === "stop") {
        sendBtn.classList.add("stop-btn");
        sendBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="6" y="6" width="12" height="12"></rect>
            </svg>
        `;
        sendBtn.disabled = false;
    } else {
        sendBtn.classList.remove("stop-btn");
        sendBtn.innerHTML = `
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
            </svg>
        `;
        // Send button disabled state depends on context
    }
}
async function updateTaskSummary(sessionId, userMessage, assistantResponse) {
    // Generate a summary from the conversation
    const summaryText = assistantResponse.substring(0, 200) +
        (assistantResponse.length > 200 ? "..." : "");

    try {
        await fetch(`/api/sessions/${sessionId}/update-summary`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({
                user_message: userMessage,
                assistant_response: assistantResponse,
                summary: summaryText
            }),
        });
    } catch (error) {
        console.error("Failed to update task summary:", error);
    }
}
