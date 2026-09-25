import sys
import tty
import termios
import subprocess
import sqlite3
import uuid
import warnings
from datetime import datetime
from pathlib import Path

from langchain.agents import create_agent
from langchain.tools import tool
from langchain_community.tools import DuckDuckGoSearchRun
from langgraph.checkpoint.sqlite import SqliteSaver
from dotenv import load_dotenv

load_dotenv()
warnings.filterwarnings("ignore")

ROOT = Path(__file__).parent.resolve()
PROTECTED = {".env", "agent_state.db"}
MAX_READ_CHARS = 20_000

# ---------------------------------------------------------------------------
# Database & Checkpointer Setup (SQLite for chat sessions & memory)
# ---------------------------------------------------------------------------
DB_PATH = ROOT / "agent_state.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                thread_id TEXT PRIMARY KEY,
                title TEXT,
                updated_at TEXT
            )
        """)

init_db()

def save_chat_metadata(thread_id: str, title: str):
    now = datetime.now().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO chat_sessions (thread_id, title, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET title = excluded.title, updated_at = excluded.updated_at
            """,
            (thread_id, title, now)
        )

def get_chat_sessions():
    cursor = conn.cursor()
    cursor.execute("SELECT thread_id, title, updated_at FROM chat_sessions ORDER BY updated_at DESC")
    return cursor.fetchall()


# ---------------------------------------------------------------------------
# Sandbox File and Utility Tools
# ---------------------------------------------------------------------------
def _safe_path(relative_path: str) -> Path:
    path = (ROOT / relative_path).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError(f"Access denied: '{relative_path}' is outside the project folder.")
    if path.name in PROTECTED:
        raise ValueError(f"Access denied: '{path.name}' is protected.")
    return path


@tool
def list_files(subfolder: str = ".") -> str:
    """List files and folders in the project folder (or a subfolder of it)."""
    try:
        folder = (ROOT / subfolder).resolve()
        if not folder.is_relative_to(ROOT) or not folder.is_dir():
            return f"'{subfolder}' is not a valid folder in the project."
        entries = []
        for p in sorted(folder.iterdir()):
            if p.name.startswith(".") or p.name in PROTECTED or p.name == "__pycache__":
                continue
            kind = "dir " if p.is_dir() else "file"
            entries.append(f"[{kind}] {p.relative_to(ROOT)}")
        return "\n".join(entries) or "(empty folder)"
    except Exception as e:
        return f"Error: {e}"


@tool
def read_file(path: str) -> str:
    """Read the text contents of a file, given its path relative to the project folder."""
    try:
        p = _safe_path(path)
        if not p.is_file():
            return f"File not found: {path}"
        text = p.read_text(encoding="utf-8")
        if len(text) > MAX_READ_CHARS:
            return text[:MAX_READ_CHARS] + f"\n\n[... truncated, {len(text)} chars total]"
        return text
    except UnicodeDecodeError:
        return f"'{path}' is not a text file."
    except Exception as e:
        return f"Error: {e}"


@tool
def write_file(path: str, content: str) -> str:
    """Create a new file or completely overwrite an existing one."""
    try:
        p = _safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        existed = p.exists()
        p.write_text(content, encoding="utf-8")
        return f"{'Overwrote' if existed else 'Created'} {path} ({len(content)} chars)."
    except Exception as e:
        return f"Error: {e}"


@tool
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace one exact snippet of text in a file. old_text must appear exactly once."""
    try:
        p = _safe_path(path)
        if not p.is_file():
            return f"File not found: {path}"
        text = p.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count == 0:
            return "old_text was not found. Read the file and copy the text exactly."
        if count > 1:
            return f"old_text appears {count} times. Include more surrounding text to make it unique."
        p.write_text(text.replace(old_text, new_text), encoding="utf-8")
        return f"Edited {path}."
    except Exception as e:
        return f"Error: {e}"


@tool
def run_command(command: str) -> str:
    """Run a shell command (e.g. pytest, python script, git status) in the project root."""
    try:
        res = subprocess.run(
            command, shell=True, cwd=ROOT, capture_output=True, text=True, timeout=30
        )
        out = res.stdout
        if res.stderr:
            out += f"\nSTDERR:\n{res.stderr}"
        return out or "(command executed successfully with no output)"
    except Exception as e:
        return f"Error executing command: {e}"


search_run = DuckDuckGoSearchRun()

@tool
def search_web(query: str) -> str:
    """Search the web for documentation, library guides, and technical solutions."""
    try:
        return search_run.run(query)
    except Exception as e:
        return f"Search failed: {e}"


# ---------------------------------------------------------------------------
# Agent Setup
# ---------------------------------------------------------------------------
checkpointer = SqliteSaver(conn)
agent = create_agent(
    model="google_genai:gemini-3.5-flash-lite",
    tools=[list_files, read_file, write_file, edit_file, run_command, search_web],
    system_prompt=(
        "You are an extremely impactful and versatile assistant with access to the user's "
        "project folder, shell command runner, and web search. Use your tools proactively "
        "to explore, write code, run tests, and research documentation. "
        "Briefly tell the user what you changed or found."
    ),
    checkpointer=checkpointer,
)


def summarize_chat_title(thread_id: str) -> str:
    """Ask the agent to generate a short 3-5 word title summarizing the chat session."""
    try:
        config = {"configurable": {"thread_id": thread_id}}
        res = agent.invoke(
            {"messages": [{"role": "user", "content": "Summarize this entire chat session in a short, punchy 3-6 word title (no punctuation, no quotes). Return ONLY the title."}]},
            config=config,
        )
        if res["messages"]:
            title = res["messages"][-1].text.strip().strip('"\'')
            if len(title) > 0 and len(title) < 60:
                return title
    except Exception:
        pass
    return f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"


# ---------------------------------------------------------------------------
# Terminal Arrow-Key Picker for /resume & Command Palette
# ---------------------------------------------------------------------------
def run_picker(items: list[tuple[str, str]], title: str = "Select an item:") -> int | None:
    """
    Renders an interactive menu navigated with Up/Down arrows and Enter.
    items: list of (display_text, value_identifier)
    Returns index of selected item, or None if cancelled.
    """
    if not items:
        print("No items available.")
        return None

    selected = 0
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)

    def print_menu():
        # Clear previous lines & print menu
        sys.stdout.write(f"\033[1m{title}\033[0m (Use ↑/↓ arrows, Enter to select, q to cancel)\n")
        for i, (disp, _) in enumerate(items):
            if i == selected:
                sys.stdout.write(f" \033[1;36m> {disp}\033[0m\n")  # Cyan & Bold
            else:
                sys.stdout.write(f"   {disp}\n")
        sys.stdout.flush()

    # Initial draw (move cursor back up afterwards)
    print_menu()
    num_lines = len(items) + 1

    try:
        tty.setraw(fd)
        while True:
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                ch2 = sys.stdin.read(2)
                if ch2 == '[A':  # Up arrow
                    selected = (selected - 1) % len(items)
                elif ch2 == '[B':  # Down arrow
                    selected = (selected + 1) % len(items)
            elif ch == '\r' or ch == '\n':  # Enter
                # Clear menu lines
                sys.stdout.write(f"\033[{num_lines}A\033[J")
                sys.stdout.flush()
                return selected
            elif ch.lower() == 'q' or ch == '\x03':  # q or Ctrl+C
                sys.stdout.write(f"\033[{num_lines}A\033[J")
                sys.stdout.flush()
                return None

            # Redraw menu
            sys.stdout.write(f"\033[{num_lines}A\033[J")
            print_menu()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# ---------------------------------------------------------------------------
# Main REPL
# ---------------------------------------------------------------------------
def print_help():
    print("\n--- Command Palette & Help ---")
    print("  /help           - Show this help menu")
    print("  /palette        - Open interactive command palette")
    print("  /resume         - Pick and resume a previous chat session")
    print("  /sessions       - List all saved chat sessions")
    print("  /new            - Start a brand new chat session")
    print("  /exit           - Save summary and exit chat")
    print("------------------------------\n")


def command_palette_menu(current_thread_id: str) -> str | None:
    """Interactive command palette using the arrow picker."""
    palette_options = [
        ("Resume a previous chat session (/resume)", "resume"),
        ("Start a brand new chat session (/new)", "new"),
        ("List all saved chat sessions (/sessions)", "sessions"),
        ("Show help and available commands (/help)", "help"),
        ("Exit application (/exit)", "exit"),
    ]
    disp_items = [opt[0] for opt in palette_options]
    idx = run_picker([(d, palette_options[i][1]) for i, d in enumerate(disp_items)], title="⚡ Command Palette:")
    if idx is not None:
        cmd = palette_options[idx][1]
        if cmd == "resume":
            return handle_resume(current_thread_id)
        elif cmd == "new":
            return handle_new(current_thread_id)
        elif cmd == "sessions":
            handle_sessions()
        elif cmd == "help":
            print_help()
        elif cmd == "exit":
            return "EXIT"
    return current_thread_id


def handle_resume(current_thread_id: str) -> str:
    sessions = get_chat_sessions()
    if not sessions:
        print("\nNo previous chat sessions found.\n")
        return current_thread_id

    items = []
    for tid, title, updated_at in sessions:
        display_title = title or f"Session {tid[:8]}"
        display_str = f"{display_title} (Last active: {updated_at[:19]})"
        items.append((display_str, tid))

    idx = run_picker(items, title="📂 Select a chat session to resume:")
    if idx is not None:
        chosen_tid = items[idx][1]
        print(f"\n--- Resumed Session: {items[idx][0]} (Thread: {chosen_tid[:8]}) ---\n")
        return chosen_tid
    return current_thread_id


def handle_new(current_thread_id: str) -> str:
    # Save current session title before switching
    if current_thread_id:
        title = summarize_chat_title(current_thread_id)
        save_chat_metadata(current_thread_id, title)

    new_tid = str(uuid.uuid4())
    print(f"\n--- Started New Chat Session (Thread: {new_tid[:8]}) ---\n")
    return new_tid


def handle_sessions():
    sessions = get_chat_sessions()
    if not sessions:
        print("\nNo saved chat sessions.\n")
        return
    print("\n--- Saved Chat Sessions ---")
    for tid, title, updated_at in sessions:
        print(f"• [{tid[:8]}] {title or 'Untitled'} (Updated: {updated_at[:19]})")
    print("---------------------------\n")


def main():
    current_thread_id = str(uuid.uuid4())
    print(f"============================================================")
    print(f"🚀 AI Agent CLI Initialized (Thread: {current_thread_id[:8]})")
    print(f"📁 Workspace: {ROOT}")
    print(f"💡 Type your prompt or type '/' for command palette / '/help'")
    print(f"============================================================")

    while True:
        try:
            prompt = input("\nPrompt > ").strip()
            if not prompt:
                continue

            # Command handling
            if prompt == "/exit":
                print("Summarizing chat session...")
                title = summarize_chat_title(current_thread_id)
                save_chat_metadata(current_thread_id, title)
                print(f"Saved session as: '{title}'. Goodbye!")
                break
            elif prompt == "/sessions":
                handle_sessions()
                continue
            elif prompt == "/resume":
                current_thread_id = handle_resume(current_thread_id)
                continue
            elif prompt == "/new":
                current_thread_id = handle_new(current_thread_id)
                continue
            elif prompt == "/help":
                print_help()
                continue
            elif prompt == "/palette" or prompt == "/":
                res = command_palette_menu(current_thread_id)
                if res == "EXIT":
                    print("Summarizing chat session...")
                    title = summarize_chat_title(current_thread_id)
                    save_chat_metadata(current_thread_id, title)
                    print(f"Saved session as: '{title}'. Goodbye!")
                    break
                elif res:
                    current_thread_id = res
                continue

            # Run agent invocation
            config = {"configurable": {"thread_id": current_thread_id}}
            result = agent.invoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config=config,
            )

            if result["messages"]:
                print(f"\nAgent: {result['messages'][-1].text}")
                # Save metadata update on interaction
                title = summarize_chat_title(current_thread_id)
                save_chat_metadata(current_thread_id, title)

        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nUse /exit to quit.")
        except Exception as e:
            print(f"\nAn error occurred: {e}")


if __name__ == "__main__":
    main()