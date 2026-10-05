# AI Agents CLI Workspace

An interactive, feature-rich AI Agent CLI built with **Python**, **LangChain**, **LangGraph**, and **Google GenAI (Gemini)**.

---

## Features

- **Interactive REPL & Command Palette**: Run prompts or use `/palette` (or `/`) for an interactive terminal arrow-key menu.
- **Session Management & Persistence**: SQLite-backed checkpointer (`agent_state.db`) automatically saves conversations, tracks chat histories, and allows you to resume past sessions with `/resume`. AI auto-summarizes chat titles.
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
