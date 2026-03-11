# Bookmark Quick Jump

A [Zed](https://zed.dev) extension that gives you **10 numbered bookmark slots
(0-9)**, each capable of holding multiple file locations.

| Action | Shortcut |
|--------|----------|
| **Jump** to the next location in slot N | `Ctrl+N` |
| **Toggle** the current cursor position in slot N | `Ctrl+Shift+N` |

Pressing `Ctrl+1` a second time while already at a bookmark cycles to the *next*
location stored in that slot, wrapping around.

---

## Installation

### Prerequisites

Before installing, make sure you have:

1. **Zed ≥ 0.205** (for extension API v0.7.0)
2. **Rust** with the `wasm32-wasip2` target — Zed compiles extensions to
   WebAssembly, so this target is required. Install it with:
   ```sh
   rustup target add wasm32-wasip2
   ```
3. **Python 3** — used by the helper script that persists bookmarks across
   sessions. Verify it is installed:
   - **macOS / Linux:** `python3 --version`
   - **Windows:** `python --version`
4. **`zed` CLI in your PATH** — needed for keyboard-shortcut navigation.
   In Zed, open the command palette and run `zed: install cli`.

> **Windows note:** If "Install Dev Extension" appears to do nothing, the most
> common cause is a missing `wasm32-wasip2` Rust target. Run the `rustup`
> command above and try again. Check Zed's log (`zed: open log`) for errors.

### Step 1 — Install the extension

1. Open the **Extensions** view (`zed: extensions` in the command palette).
2. Click **Install Dev Extension**.
3. Choose the directory where you cloned this repository.

Zed compiles the extension to WebAssembly automatically. If the compilation
fails silently, open the Zed log (`zed: open log` in the command palette) to
see error details.

### Step 2 — Add the tasks

Copy the task definitions into your global Zed tasks file. If the file already
exists, merge the array contents.

<details>
<summary><strong>macOS / Linux</strong></summary>

Copy from [`config/tasks.json`](config/tasks.json) into
`~/.config/zed/tasks.json`.

</details>

<details>
<summary><strong>Windows</strong></summary>

Copy from [`config/tasks-windows.json`](config/tasks-windows.json) into
`%APPDATA%\Zed\tasks.json`.

> The Windows variant uses `python` instead of `python3` because on Windows
> the Python 3 executable installed from python.org or the Microsoft Store is
> named `python`.

</details>

The tasks use `$ZED_FILE`, `$ZED_ROW`, and `$ZED_COLUMN` — variables that Zed
automatically injects to reflect the active editor position.

### Step 3 — Add the keybindings

Copy the keybindings from [`config/keymap.json`](config/keymap.json) into your
global Zed keymap:

| Platform | Keymap path |
|----------|-------------|
| macOS / Linux | `~/.config/zed/keymap.json` |
| Windows | `%APPDATA%\Zed\keymap.json` |

Merge them with any existing entries.

> **Tip:** If `Ctrl+1`…`Ctrl+9` conflict with your tab-switching shortcuts,
> rename the bindings (e.g., `ctrl-alt-1`) in your keymap file.

---

## Usage

### Keyboard shortcuts (after Step 2 & 3)

```
Ctrl+Shift+1  →  Toggle the current line in bookmark slot 1
               (first press = set, second press on same line = remove)

Ctrl+1        →  Jump to the next location stored in slot 1
               (pressing again cycles to the next location)
```

The same pattern applies to slots 0-9.

### AI assistant slash command

The extension also registers a `/bookmark` slash command in the Zed AI panel:

```
/bookmark set 1 src/main.rs:42          — add line 42 of main.rs to slot 1
/bookmark set 1 src/main.rs:42:8        — same, with column 8
/bookmark jump 1                        — show the next location in slot 1
/bookmark list                          — show all bookmarks
/bookmark clear 1                       — remove all bookmarks from slot 1
/bookmark clear all                     — remove every bookmark
/bookmark help                          — show usage
```

> The slash-command state lives in memory for the current Zed session.
> Keyboard-shortcut state (from the helper script) persists across sessions in a
> platform-specific location:
>
> | Platform | Bookmark file |
> |----------|---------------|
> | macOS / Linux | `~/.local/share/zed-bookmarks/bookmarks.json` |
> | Windows | `%LOCALAPPDATA%\zed-bookmarks\bookmarks.json` |

---

## How it works

```
┌──────────────────────────────────────────────┐
│              Zed editor                       │
│                                               │
│  Ctrl+Shift+1                                 │
│      └─► task::Spawn tag:"bookmark-set-1"     │
│              └─► bookmark.py set 1            │
│                  $ZED_FILE                    │
│                  $ZED_ROW                     │
│                  $ZED_COLUMN                  │
│                  └─► writes to                │
│                      bookmarks.json           │
│                                               │
│  Ctrl+1                                       │
│      └─► task::Spawn tag:"bookmark-jump-1"    │
│              └─► bookmark.py jump 1           │
│                  └─► reads next pos           │
│                      zed file:ln:col          │
│                      (IPC → navigate)         │
└──────────────────────────────────────────────┘
```

Navigation is performed by calling the `zed` CLI, which sends an IPC message to
the running Zed instance and opens the target location in your existing window.

---

## Requirements

- Zed ≥ 0.205 (for extension API v0.7.0)
- Rust + `wasm32-wasip2` target (for building the extension)
- Python 3 (for the helper script)
- `zed` in your `$PATH` / `%PATH%` (for keyboard-shortcut-based navigation)

---

## Troubleshooting

### "Install Dev Extension" does nothing

1. **Verify the Rust WASM target is installed:**
   ```sh
   rustup target add wasm32-wasip2
   ```
2. **Check Zed's log** for compilation errors — open the command palette and run
   `zed: open log`.
3. **Make sure you selected the repository root** (the directory containing
   `extension.toml`) when prompted.

### `python3` not found (Windows)

On Windows, the Python executable is usually called `python` or `py` rather than
`python3`. Use the task definitions from
[`config/tasks-windows.json`](config/tasks-windows.json) which reference `py`
(the [Python Launcher for Windows](https://docs.python.org/3/using/windows.html#python-launcher-for-windows)).

> **Tip:** If `py` is not available either, replace the `"command"` value in the
> task definitions with whichever command starts Python 3 on your system (e.g.
> `python`).

### Running the built-in diagnostic

The extension ships a `diagnose` subcommand that checks your environment in one
step:

```sh
# macOS / Linux
python3 scripts/bookmark.py diagnose

# Windows
py scripts/bookmark.py diagnose
```

Or run the **bookmark-diagnose** task from Zed's command palette. The task is
configured with `"reveal": "always"` so output is always visible.

You can also enable **verbose tracing** for any command by passing `--verbose`
(or `-v`), or by setting `BOOKMARK_VERBOSE=1`:

```sh
python3 scripts/bookmark.py --verbose set 1 src/main.rs 42
BOOKMARK_VERBOSE=1 python3 scripts/bookmark.py jump 1
```

### Bookmarks not persisting

The helper script stores bookmarks in a JSON file. Make sure the data directory
is writable:

| Platform | Default path |
|----------|-------------|
| macOS / Linux | `~/.local/share/zed-bookmarks/` |
| Windows | `%LOCALAPPDATA%\zed-bookmarks\` |

You can override the location by setting the `BOOKMARK_FILE` environment
variable.

### Keyboard shortcut opens a Run/Debug/Attach/Launch dialog

If pressing `Ctrl+Shift+1` (or any bookmark shortcut) opens a dialog with
Run/Debug/Attach/Launch tabs instead of setting the bookmark, the task
definitions are not being found by Zed. This typically happens when:

1. **Tasks are not installed** — make sure you have copied the task definitions
   from `config/tasks.json` (or `config/tasks-windows.json` on Windows) into
   your global Zed tasks file. See [Step 2](#step-2--add-the-tasks) above.
2. **Keybindings are outdated** — the keybindings now use `task_tag` (tag-based
   matching) instead of `task_name` (label-based matching), and the context is
   `"Workspace"` rather than `"Editor"`. Re-copy the keybindings from
   [`config/keymap.json`](config/keymap.json). See [Step 3](#step-3--add-the-keybindings).
3. **Task definitions are outdated** — each task must include a `"tags"` field
   that matches the `task_tag` in the keybinding. Re-copy the task definitions.

---

## Repository layout

```
bookmark-quick-jump/
├── extension.toml            ← Zed extension manifest
├── Cargo.toml                ← Rust build config (WASM)
├── src/
│   └── lib.rs                ← Slash-command implementation
├── scripts/
│   ├── bookmark.py           ← Cross-platform bookmark helper (Python 3)
│   └── bookmark.sh           ← Legacy bash helper (macOS / Linux only)
├── config/
│   ├── tasks.json            ← Task definitions for macOS / Linux
│   ├── tasks-windows.json    ← Task definitions for Windows
│   └── keymap.json           ← Keybindings (all platforms)
└── README.md
```
