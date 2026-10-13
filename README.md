# AI Agents CLI Workspace

An interactive, feature-rich AI Agent CLI built with **Python**, **LangChain**, **LangGraph**, and **Google GenAI (Gemini)**.

---

## Features

- **Interactive REPL & Command Palette**: Run prompts or use `/palette` (or `/`) for an interactive terminal arrow-key menu.
- **Session Management & Persistence**: SQLite-backed checkpointer automatically saves conversations, tracks chat histories, and allows you to resume past sessions with `/resume`. AI auto-summarizes chat titles. Chat logs are stored privately outside the repo (see [Chat History & Privacy](#chat-history--privacy)).
- **Built-in Sandbox Tools**:
  - `list_files` / `read_file` / `write_file` / `edit_file`: Safe, sandboxed workspace file management.
  - `run_command`: Execute shell commands (e.g., `pytest`, `git status`) directly in the project root.
  - `search_web`: DuckDuckGo web search integration.
- **Ethical Reflections**: Explores profound questions on AI, human agency, and spiritual stewardship (`ethics.md`).

---

## Project Structure

```text
├── main.py            # Main application (REPL, tools, agent setup, SQLite checkpointer)
├── ethics.md          # Core ethical questions regarding AI and human agency
├── pyproject.toml     # Project configuration and dependencies (uv package manager)
├── uv.lock            # Lockfile for reproducible builds
└── src/               # Package source files
```

---

## Chat History & Privacy

Chat logs are **never stored in the project folder**, so they can't be committed or pushed. They live in a private, user-only directory:

| Setting | Location |
|---|---|
| Default | `~/.local/share/agents/agent_state.db` (or `$XDG_DATA_HOME/agents/`) |
| Override | set `AGENTS_DATA_DIR=/path/to/dir` in your environment or `.env` |

The directory is created with `700` permissions and the database with `600`. If an older `agent_state.db` is found in the project folder, it is moved to the new location automatically on first run. `*.db` files are also git-ignored as a safety net.

---

## Getting Started

### Prerequisites

- Python `>= 3.14`
- [uv](https://github.com/astral-sh/uv) (recommended) or `pip`
- A Google GenAI API Key set in your environment as `GOOGLE_API_KEY` (or in a `.env` file).

### Installation

1. Clone or open the repository.
2. Install dependencies using `uv`:
   ```bash
   uv sync
   ```

3. Set up your `.env` file with your API key:
   ```env
   GOOGLE_API_KEY=your_gemini_api_key_here
   ```

---

## Usage

Run the agent REPL using `uv`:

```bash
uv run python main.py
```

### Available Commands in REPL

- `/help` or `/?` - Show help menu & available commands
- `/palette` or `/` - Open interactive command palette (arrow-key navigation)
- `/resume` - Pick and resume a previous chat session
- `/sessions` - List all saved chat sessions
- `/new` - Start a brand new chat session
- `/exit` - Save session summary and exit
