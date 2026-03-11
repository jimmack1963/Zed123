#!/usr/bin/env python3
"""bookmark.py — cross-platform helper script for Bookmark Quick Jump (Zed extension)

Usage:
  bookmark.py set   <slot> <file> <line> [<col>]   Toggle a bookmark for the
                                                     given slot (0-9).  Running
                                                     the same command twice
                                                     removes the bookmark.

  bookmark.py jump  <slot>                          Navigate to the next
                                                     bookmark in the slot.
                                                     Cycles through all stored
                                                     positions.

  bookmark.py list  [<slot>]                        Print stored bookmarks.

  bookmark.py clear <slot>|all                      Remove bookmarks.

  bookmark.py diagnose                              Check Python, paths, zed
                                                     CLI, and env — useful for
                                                     debugging silent failures.

Options:
  --verbose / -v       Print step-by-step trace to stderr.
                       Also enabled by setting BOOKMARK_VERBOSE=1.

The script persists state in:
  $BOOKMARK_FILE   (env override)

  Linux/macOS:  ~/.local/share/zed-bookmarks/bookmarks.json   (default)
  Windows:      %LOCALAPPDATA%\\zed-bookmarks\\bookmarks.json  (default)

Navigation is performed by calling the `zed` CLI with
  zed <file>:<line>:<col>
which tells a running Zed instance to open that location.
"""

import json
import os
import platform
import shutil
import subprocess
import sys

# ── verbose logging ───────────────────────────────────────────────────────────

VERBOSE = os.environ.get("BOOKMARK_VERBOSE", "") not in ("", "0", "false")


def log(msg):
    """Print a diagnostic message to stderr when verbose mode is enabled."""
    if VERBOSE:
        print(f"[bookmark] {msg}", file=sys.stderr)


def get_default_bookmark_dir():
    """Return the default directory for storing bookmark state."""
    if platform.system() == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        return os.path.join(base, "zed-bookmarks")
    return os.path.join(
        os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
        "zed-bookmarks",
    )


def get_bookmark_file():
    """Return the path to the bookmarks JSON file."""
    explicit = os.environ.get("BOOKMARK_FILE")
    if explicit:
        return explicit
    bookmark_dir = os.environ.get("BOOKMARK_FILE_DIR", get_default_bookmark_dir())
    return os.path.join(bookmark_dir, "bookmarks.json")


def ensure_file(path):
    """Create the bookmark file and its parent directory if they don't exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.isfile(path):
        with open(path, "w") as f:
            json.dump({}, f)


def load(path):
    """Load and return the JSON data from *path*."""
    with open(path, "r") as f:
        return json.load(f)


def save(path, data):
    """Write *data* as JSON to *path*."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


# ── commands ──────────────────────────────────────────────────────────────────


def cmd_set(path, slot, file, line, col):
    """Toggle a bookmark position in a slot."""
    log(f"set: slot={slot} file={file} line={line} col={col}")
    # Normalize to absolute path
    file = os.path.abspath(file)
    log(f"set: resolved file to {file}")
    data = load(path)
    positions = data.get(slot, [])
    entry = {"file": file, "line": int(line), "col": int(col)}

    if entry in positions:
        positions.remove(entry)
        print(f"Removed bookmark {slot}: {file}:{line}:{col}")
    else:
        positions.append(entry)
        print(
            f"Set bookmark {slot}: {file}:{line}:{col}"
            f"  ({len(positions)} location(s) in slot)"
        )

    if positions:
        data[slot] = positions
    elif slot in data:
        del data[slot]

    # Reset cycle index when toggling
    idx_key = f"_idx_{slot}"
    if idx_key in data:
        del data[idx_key]

    save(path, data)
    log(f"set: saved to {path}")


def cmd_jump(path, slot):
    """Navigate to the next bookmark in a slot."""
    log(f"jump: slot={slot}")
    data = load(path)
    positions = data.get(slot, [])

    if not positions:
        print(f"No bookmarks in slot {slot}", file=sys.stderr)
        log("jump: no bookmarks found in slot")
        return

    idx_key = f"_idx_{slot}"
    idx = data.get(idx_key, 0) % len(positions)
    entry = positions[idx]
    target = f"{entry['file']}:{entry['line']}:{entry['col']}"
    print(f"Jumping to {target}")

    # Advance index
    data[idx_key] = (idx + 1) % len(positions)
    save(path, data)

    # Open in the current Zed instance (single-instance IPC)
    zed_cmd = shutil.which("zed")
    if zed_cmd:
        log(f"jump: running {zed_cmd} {target}")
        subprocess.run([zed_cmd, target])
    else:
        log("jump: 'zed' not found in PATH")
        print(
            "WARNING: 'zed' not found in PATH; cannot navigate automatically.",
            file=sys.stderr,
        )
        print(f"Open manually: {target}", file=sys.stderr)


def cmd_list(path, slot_filter=None):
    """Print stored bookmarks."""
    data = {
        k: v for k, v in load(path).items() if not k.startswith("_idx_")
    }
    if not data:
        print("No bookmarks set.")
        return

    for slot in sorted(data):
        if slot_filter and slot != slot_filter:
            continue
        for entry in data[slot]:
            print(f"  Slot {slot}: {entry['file']}:{entry['line']}:{entry['col']}")


def cmd_clear(path, slot):
    """Remove bookmarks from a slot (or all slots)."""
    if slot == "all":
        save(path, {})
        print("All bookmarks cleared.")
    else:
        data = load(path)
        for key in [slot, f"_idx_{slot}"]:
            data.pop(key, None)
        save(path, data)
        print(f"Bookmarks for slot {slot} cleared.")


def print_help():
    """Print the docstring header as usage information."""
    for line in __doc__.strip().splitlines():
        print(line)


def cmd_diagnose():
    """Check the full bookmark pipeline and report potential problems."""
    ok = True

    # 1. Python
    print(f"Python executable : {sys.executable}")
    print(f"Python version    : {sys.version}")

    # 2. Bookmark file
    path = get_bookmark_file()
    print(f"Bookmark file     : {path}")
    bdir = os.path.dirname(path)
    if os.path.isfile(path):
        print(f"  exists          : yes")
        try:
            data = load(path)
            count = sum(
                1 for k, v in data.items()
                if not k.startswith("_idx_") and isinstance(v, list)
            )
            print(f"  slots with data : {count}")
        except Exception as e:
            print(f"  ERROR reading   : {e}")
            ok = False
    elif os.path.isdir(bdir):
        print(f"  exists          : no (directory exists, file will be created on first use)")
    else:
        print(f"  exists          : no (directory {bdir} does not exist yet)")

    if os.path.isdir(bdir):
        writable = os.access(bdir, os.W_OK)
        print(f"  directory writable : {writable}")
        if not writable:
            ok = False
    else:
        print(f"  directory writable : (will be created on first use)")

    # 3. zed CLI
    zed_cmd = shutil.which("zed")
    if zed_cmd:
        print(f"zed CLI           : {zed_cmd}")
    else:
        print("zed CLI           : NOT FOUND in PATH")
        print("  (jump commands will not be able to navigate automatically)")
        ok = False

    # 4. Environment variables (set by Zed task runner)
    for var in ("ZED_FILE", "ZED_ROW", "ZED_COLUMN"):
        val = os.environ.get(var)
        if val:
            print(f"${var:16s}: {val}")
        else:
            print(f"${var:16s}: not set (normal outside a Zed task)")

    # 5. Platform
    print(f"Platform          : {platform.system()} {platform.release()}")

    # 6. Summary
    print()
    if ok:
        py_cmd = "py" if platform.system() == "Windows" else "python3"
        print("All checks passed. If bookmarks still aren't working, run a")
        print("task with BOOKMARK_VERBOSE=1 to see step-by-step output, e.g.:")
        print(f"  BOOKMARK_VERBOSE=1 {py_cmd} scripts/bookmark.py set 1 test.py 1")
    else:
        print("Some checks FAILED — see above for details.")


# ── dispatch ──────────────────────────────────────────────────────────────────


def main():
    global VERBOSE
    args = sys.argv[1:]

    # Allow --verbose / -v anywhere in args
    if "--verbose" in args or "-v" in args:
        VERBOSE = True
        args = [a for a in args if a not in ("--verbose", "-v")]

    command = args[0] if args else "help"
    rest = args[1:]

    log(f"command={command} args={rest}")
    log(f"python={sys.executable}")

    if command == "diagnose":
        cmd_diagnose()
        return

    path = get_bookmark_file()
    log(f"bookmark_file={path}")
    ensure_file(path)

    if command == "set":
        if len(rest) < 3:
            print("Usage: bookmark.py set <slot> <file> <line> [<col>]", file=sys.stderr)
            sys.exit(1)
        slot, file, line = rest[0], rest[1], rest[2]
        col = rest[3] if len(rest) > 3 else "0"
        cmd_set(path, slot, file, line, col)
    elif command == "jump":
        if len(rest) < 1:
            print("Usage: bookmark.py jump <slot>", file=sys.stderr)
            sys.exit(1)
        cmd_jump(path, rest[0])
    elif command == "list":
        cmd_list(path, rest[0] if rest else None)
    elif command == "clear":
        if len(rest) < 1:
            print("Usage: bookmark.py clear <slot>|all", file=sys.stderr)
            sys.exit(1)
        cmd_clear(path, rest[0])
    elif command in ("help", "--help", "-h"):
        print_help()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Usage: bookmark.py {set|jump|list|clear|diagnose|help}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
