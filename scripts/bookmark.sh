#!/usr/bin/env bash
# bookmark.sh — helper script for Bookmark Quick Jump (Zed extension)
#
# Usage:
#   bookmark.sh set   <slot> <file> <line> [<col>]   Toggle a bookmark for the
#                                                      given slot (0-9).  Running
#                                                      the same command twice
#                                                      removes the bookmark.
#
#   bookmark.sh jump  <slot>                          Navigate to the next
#                                                      bookmark in the slot.
#                                                      Cycles through all stored
#                                                      positions.
#
#   bookmark.sh list  [<slot>]                        Print stored bookmarks.
#
#   bookmark.sh clear <slot>|all                      Remove bookmarks.
#
# The script persists state in:
#   $BOOKMARK_FILE   (env override)
#   ~/.local/share/zed-bookmarks/bookmarks.json   (default)
#
# Navigation is performed by calling the `zed` CLI with
#   zed <file>:<line>:<col>
# which tells a running Zed instance to open that location.

set -euo pipefail

# ── state file ────────────────────────────────────────────────────────────────
BOOKMARK_DIR="${BOOKMARK_FILE_DIR:-$HOME/.local/share/zed-bookmarks}"
BOOKMARK_FILE="${BOOKMARK_FILE:-$BOOKMARK_DIR/bookmarks.json}"

ensure_file() {
    mkdir -p "$(dirname "$BOOKMARK_FILE")"
    if [[ ! -f "$BOOKMARK_FILE" ]]; then
        echo '{}' > "$BOOKMARK_FILE"
    fi
}

# ── json helpers (pure bash + python3 fallback) ───────────────────────────────
# We rely on python3 for JSON manipulation since `jq` is not always present.

py_read() {
    # py_read <slot>  →  prints JSON array of positions, or '[]'
    local slot="$1"
    python3 - "$BOOKMARK_FILE" "$slot" <<'PYEOF'
import sys, json
data = json.load(open(sys.argv[1]))
print(json.dumps(data.get(sys.argv[2], [])))
PYEOF
}

py_write() {
    # py_write <slot> <json-array>  →  writes updated file
    local slot="$1"
    local arr="$2"
    python3 - "$BOOKMARK_FILE" "$slot" "$arr" <<'PYEOF'
import sys, json
path, slot, arr = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path))
parsed = json.loads(arr)
if parsed:
    data[slot] = parsed
elif slot in data:
    del data[slot]
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
PYEOF
}

py_next() {
    # py_next <slot>  →  prints "file:line:col" of next position and advances index
    local slot="$1"
    python3 - "$BOOKMARK_FILE" "$slot" <<'PYEOF'
import sys, json

path, slot = sys.argv[1], sys.argv[2]
data = json.load(open(path))
positions = data.get(slot, [])
if not positions:
    sys.exit(1)

# index is stored alongside positions as a meta key _idx_<slot>
idx_key = f"_idx_{slot}"
idx = data.get(idx_key, 0) % len(positions)
entry = positions[idx]
print(f"{entry['file']}:{entry['line']}:{entry['col']}")

# advance
data[idx_key] = (idx + 1) % len(positions)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
PYEOF
}

# ── commands ──────────────────────────────────────────────────────────────────

cmd_set() {
    local slot="$1" file="$2" line="${3:?'line number required'}" col="${4:-0}"
    # Normalise to absolute path
    file="$(realpath -m "$file" 2>/dev/null || echo "$file")"
    ensure_file

    python3 - "$BOOKMARK_FILE" "$slot" "$file" "$line" "$col" <<'PYEOF'
import sys, json

path, slot, file, line, col = sys.argv[1:]
line, col = int(line), int(col)
data = json.load(open(path))
positions = data.get(slot, [])
entry = {"file": file, "line": line, "col": col}

if entry in positions:
    positions.remove(entry)
    print(f"Removed bookmark {slot}: {file}:{line}:{col}")
else:
    positions.append(entry)
    print(f"Set bookmark {slot}: {file}:{line}:{col}  ({len(positions)} location(s) in slot)")

if positions:
    data[slot] = positions
elif slot in data:
    del data[slot]

# Reset cycle index when toggling
idx_key = f"_idx_{slot}"
if idx_key in data:
    del data[idx_key]

with open(path, 'w') as f:
    json.dump(data, f, indent=2)
PYEOF
}

cmd_jump() {
    local slot="$1"
    ensure_file
    local target
    if ! target="$(py_next "$slot" 2>/dev/null)"; then
        echo "No bookmarks in slot $slot" >&2
        exit 0
    fi
    echo "Jumping to $target"
    # Open in the current Zed instance (single-instance IPC)
    if command -v zed &>/dev/null; then
        zed "$target"
    else
        echo "WARNING: 'zed' not found in PATH; cannot navigate automatically." >&2
        echo "Open manually: $target" >&2
    fi
}

cmd_list() {
    ensure_file
    local slot="${1:-}"
    python3 - "$BOOKMARK_FILE" "$slot" <<'PYEOF'
import sys, json

path, slot_filter = sys.argv[1], sys.argv[2]
data = {k: v for k, v in json.load(open(path)).items() if not k.startswith('_idx_')}
if not data:
    print("No bookmarks set.")
    sys.exit(0)

for slot in sorted(data):
    if slot_filter and slot != slot_filter:
        continue
    for entry in data[slot]:
        print(f"  Slot {slot}: {entry['file']}:{entry['line']}:{entry['col']}")
PYEOF
}

cmd_clear() {
    local slot="$1"
    ensure_file
    if [[ "$slot" == "all" ]]; then
        echo '{}' > "$BOOKMARK_FILE"
        echo "All bookmarks cleared."
    else
        python3 - "$BOOKMARK_FILE" "$slot" <<'PYEOF'
import sys, json
path, slot = sys.argv[1], sys.argv[2]
data = json.load(open(path))
for key in [slot, f"_idx_{slot}"]:
    data.pop(key, None)
with open(path, 'w') as f:
    json.dump(data, f, indent=2)
print(f"Bookmarks for slot {slot} cleared.")
PYEOF
    fi
}

# ── dispatch ──────────────────────────────────────────────────────────────────
COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
    set)   cmd_set   "$@" ;;
    jump)  cmd_jump  "$@" ;;
    list)  cmd_list  "$@" ;;
    clear) cmd_clear "$@" ;;
    help|--help|-h)
        grep '^#' "$0" | head -30 | sed 's/^# \?//'
        ;;
    *)
        echo "Unknown command: $COMMAND" >&2
        echo "Usage: bookmark.sh {set|jump|list|clear|help}" >&2
        exit 1
        ;;
esac
