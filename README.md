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

### Step 1 — Install the extension

1. Open the **Extensions** view (`zed: extensions` in the command palette).
2. Click **Install Dev Extension**.
3. Choose the directory where you cloned this repository.

Zed compiles the extension to WebAssembly automatically.

### Step 2 — Make the helper script executable

```sh
chmod +x ~/.config/zed/extensions/bookmark-quick-jump/scripts/bookmark.sh
```

> **Note:** The path above assumes Zed's default extension directory. If you
> installed as a dev extension from a different path, adjust accordingly.

### Step 3 — Add the tasks

Copy the task definitions from [`config/tasks.json`](config/tasks.json) into
your global Zed tasks file (`~/.config/zed/tasks.json`). If that file already
exists, merge the array contents.

The tasks use `$ZED_FILE`, `$ZED_ROW`, and `$ZED_COLUMN` — variables that Zed
automatically injects to reflect the active editor position.

### Step 4 — Add the keybindings

Copy the keybindings from [`config/keymap.json`](config/keymap.json) into your
global Zed keymap (`~/.config/zed/keymap.json`). Merge them with any existing
entries.

> **Tip:** If `Ctrl+1`…`Ctrl+9` conflict with your tab-switching shortcuts,
> rename the bindings (e.g., `ctrl-alt-1`) in your keymap file.

---

## Usage

### Keyboard shortcuts (after Step 3 & 4)

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
> Keyboard-shortcut state (from the helper script) persists across sessions in
> `~/.local/share/zed-bookmarks/bookmarks.json`.

---

## How it works

```
┌─────────────────────────────────────┐
│              Zed editor              │
│                                      │
│  Ctrl+Shift+1                        │
│      └─► task::Spawn "bookmark-set-1"│
│              └─► bookmark.sh set 1   │
│                  $ZED_FILE           │
│                  $ZED_ROW            │
│                  $ZED_COLUMN         │
│                  └─► writes to       │
│                      bookmarks.json  │
│                                      │
│  Ctrl+1                              │
│      └─► task::Spawn "bookmark-jump-1│
│              └─► bookmark.sh jump 1  │
│                  └─► reads next pos  │
│                      zed file:ln:col │
│                      (IPC → navigate)│
└─────────────────────────────────────┘
```

Navigation is performed by calling the `zed` CLI, which sends an IPC message to
the running Zed instance and opens the target location in your existing window.

---

## Requirements

- Zed ≥ 0.205 (for extension API v0.7.0)
- Rust + `wasm32-wasip2` target (for building the extension)
- Python 3 (for the helper script)
- `zed` in your `$PATH` (for keyboard-shortcut-based navigation)

---

## Repository layout

```
bookmark-quick-jump/
├── extension.toml        ← Zed extension manifest
├── Cargo.toml            ← Rust build config (WASM)
├── src/
│   └── lib.rs            ← Slash-command implementation
├── scripts/
│   └── bookmark.sh       ← Persistent bookmark helper (bash + python3)
├── config/
│   ├── tasks.json        ← Paste into ~/.config/zed/tasks.json
│   └── keymap.json       ← Paste into ~/.config/zed/keymap.json
└── README.md
```
