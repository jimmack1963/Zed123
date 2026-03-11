use std::collections::HashMap;
use std::sync::Mutex;

use zed_extension_api::{
    self as zed, Result, SlashCommand, SlashCommandArgumentCompletion, SlashCommandOutput,
    SlashCommandOutputSection, Worktree,
};

/// State for a single bookmark slot: a list of (file_path, row, col) positions
/// and the index of the next position to visit when cycling.
struct SlotState {
    positions: Vec<(String, u32, u32)>,
    next_index: usize,
}

impl SlotState {
    fn new() -> Self {
        SlotState {
            positions: Vec::new(),
            next_index: 0,
        }
    }

    /// Toggle the given position: add if absent, remove if already present.
    /// Returns true if the position was added, false if it was removed.
    fn toggle(&mut self, file: &str, row: u32, col: u32) -> bool {
        let pos = (file.to_string(), row, col);
        if let Some(idx) = self.positions.iter().position(|p| *p == pos) {
            self.positions.remove(idx);
            // Keep next_index in-bounds after removal
            if self.next_index > 0 && self.next_index >= self.positions.len() {
                self.next_index = 0;
            }
            false
        } else {
            self.positions.push(pos);
            true
        }
    }

    /// Return the next position to visit, advancing the cyclic index.
    fn next(&mut self) -> Option<(String, u32, u32)> {
        if self.positions.is_empty() {
            return None;
        }
        let pos = self.positions[self.next_index].clone();
        self.next_index = (self.next_index + 1) % self.positions.len();
        Some(pos)
    }
}

/// All bookmark state, keyed by slot number (0-9).
struct BookmarkState {
    slots: HashMap<u8, SlotState>,
}

impl BookmarkState {
    fn new() -> Self {
        BookmarkState {
            slots: HashMap::new(),
        }
    }

    fn toggle(&mut self, slot: u8, file: &str, row: u32, col: u32) -> bool {
        self.slots.entry(slot).or_insert_with(SlotState::new).toggle(file, row, col)
    }

    fn next(&mut self, slot: u8) -> Option<(String, u32, u32)> {
        self.slots.get_mut(&slot)?.next()
    }

    fn clear_slot(&mut self, slot: u8) {
        self.slots.remove(&slot);
    }

    fn clear_all(&mut self) {
        self.slots.clear();
    }

    fn list(&self) -> Vec<(u8, &[(String, u32, u32)])> {
        let mut result: Vec<(u8, &[(String, u32, u32)])> = self
            .slots
            .iter()
            .filter(|(_, s)| !s.positions.is_empty())
            .map(|(&k, s)| (k, s.positions.as_slice()))
            .collect();
        result.sort_by_key(|(k, _)| *k);
        result
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Extension entry point
// ──────────────────────────────────────────────────────────────────────────────

struct BookmarkQuickJump {
    state: Mutex<BookmarkState>,
}

const HELP_TEXT: &str = "\
**Bookmark Quick Jump** — `/bookmark <subcommand> [args]`

Subcommands:
  `set <slot> <file>:<line>[:<col>]`   Add/remove a position from slot (0-9)
  `jump <slot>`                        Show the next position in slot (0-9)
  `list`                               List all bookmarks
  `clear <slot>`                       Remove all bookmarks from a slot
  `clear all`                          Remove every bookmark
  `help`                               Show this message

Examples:
  `/bookmark set 1 src/main.rs:42`
  `/bookmark set 1 src/main.rs:42:8`
  `/bookmark jump 1`
  `/bookmark list`
  `/bookmark clear 1`

**Keyboard shortcuts** — add the following to your Zed `tasks.json` and `keymap.json`:
See the `config/` directory in this extension for ready-made snippets.";

impl zed::Extension for BookmarkQuickJump {
    fn new() -> Self {
        BookmarkQuickJump {
            state: Mutex::new(BookmarkState::new()),
        }
    }

    fn complete_slash_command_argument(
        &self,
        _command: SlashCommand,
        args: Vec<String>,
    ) -> Result<Vec<SlashCommandArgumentCompletion>, String> {
        // Offer sub-command completions when the user hasn't typed one yet
        if args.is_empty() || (args.len() == 1 && !args[0].contains(' ')) {
            let prefix = args.first().map(String::as_str).unwrap_or("");
            let completions = ["set", "jump", "list", "clear", "help"]
                .iter()
                .filter(|s| s.starts_with(prefix))
                .map(|s| SlashCommandArgumentCompletion {
                    label: s.to_string(),
                    new_text: s.to_string(),
                    run_command: *s == "list" || *s == "help",
                })
                .collect();
            return Ok(completions);
        }
        Ok(vec![])
    }

    fn run_slash_command(
        &self,
        command: SlashCommand,
        args: Vec<String>,
        _worktree: Option<&Worktree>,
    ) -> Result<SlashCommandOutput, String> {
        if command.name != "bookmark" {
            return Err(format!("Unknown command: {}", command.name));
        }

        // Flatten args (Zed may pass them pre-split or as one string) into words
        let words: Vec<&str> = args
            .iter()
            .flat_map(|a| a.split_whitespace())
            .collect();

        match words.as_slice() {
            // ── set ──────────────────────────────────────────────────────────
            [sub, slot_str, location] if *sub == "set" => {
                let slot = parse_slot(slot_str)?;
                let (file, row, col) = parse_location(location)?;
                let mut state = self.state.lock().unwrap();
                let added = state.toggle(slot, &file, row, col);
                let count = state
                    .slots
                    .get(&slot)
                    .map(|s| s.positions.len())
                    .unwrap_or(0);
                let action = if added { "added to" } else { "removed from" };
                let text = format!(
                    "Bookmark `{}:{}:{}` {} slot {}. Slot now has {} location(s).",
                    file, row, col, action, slot, count
                );
                make_output(text)
            }

            // ── jump ─────────────────────────────────────────────────────────
            [sub, slot_str] if *sub == "jump" => {
                let slot = parse_slot(slot_str)?;
                let mut state = self.state.lock().unwrap();
                match state.next(slot) {
                    Some((file, row, col)) => {
                        let text =
                            format!("Jump to `{}:{}:{}`", file, row, col);
                        make_output(text)
                    }
                    None => make_output(format!(
                        "Slot {} has no bookmarks. Use `/bookmark set {} <file>:<line>` to add one.",
                        slot, slot
                    )),
                }
            }

            // ── list ─────────────────────────────────────────────────────────
            [sub] if *sub == "list" => {
                let state = self.state.lock().unwrap();
                let all = state.list();
                if all.is_empty() {
                    make_output(
                        "No bookmarks set. Use `/bookmark set <slot> <file>:<line>` to add one."
                            .to_string(),
                    )
                } else {
                    let mut text = String::from("**Bookmarks:**\n\n");
                    for (slot, positions) in all {
                        for (file, row, col) in positions {
                            text.push_str(&format!(
                                "- Slot **{}**: `{}:{}:{}`\n",
                                slot, file, row, col
                            ));
                        }
                    }
                    make_output(text)
                }
            }

            // ── clear all ────────────────────────────────────────────────────
            [sub, "all"] if *sub == "clear" => {
                let mut state = self.state.lock().unwrap();
                state.clear_all();
                make_output("All bookmarks cleared.".to_string())
            }

            // ── clear <slot> ─────────────────────────────────────────────────
            [sub, slot_str] if *sub == "clear" => {
                let slot = parse_slot(slot_str)?;
                let mut state = self.state.lock().unwrap();
                state.clear_slot(slot);
                make_output(format!("Bookmarks for slot {} cleared.", slot))
            }

            // ── help / empty ─────────────────────────────────────────────────
            _ => make_output(HELP_TEXT.to_string()),
        }
    }
}

// ──────────────────────────────────────────────────────────────────────────────
// Helpers
// ──────────────────────────────────────────────────────────────────────────────

fn parse_slot(s: &str) -> Result<u8, String> {
    s.parse::<u8>()
        .ok()
        .filter(|&n| n <= 9)
        .ok_or_else(|| format!("Slot must be a single digit 0-9, got: `{}`", s))
}

/// Parse `<file>:<row>[:<col>]` into `(file, row, col)`.
fn parse_location(location: &str) -> Result<(String, u32, u32), String> {
    // Split from the right so that Windows-style paths with drive letters work.
    let parts: Vec<&str> = location.rsplitn(3, ':').collect();
    match parts.as_slice() {
        // file:row:col  (parts are reversed by rsplitn)
        [col_str, row_str, file] => {
            let row = row_str
                .parse::<u32>()
                .map_err(|_| format!("Invalid line number: `{}`", row_str))?;
            let col = col_str
                .parse::<u32>()
                .map_err(|_| format!("Invalid column: `{}`", col_str))?;
            Ok((file.to_string(), row, col))
        }
        // file:row  (no column)
        [row_str, file] => {
            let row = row_str
                .parse::<u32>()
                .map_err(|_| format!("Invalid line number: `{}`", row_str))?;
            Ok((file.to_string(), row, 0))
        }
        _ => Err(format!(
            "Expected `<file>:<line>[:<col>]`, got: `{}`",
            location
        )),
    }
}

fn make_output(text: String) -> Result<SlashCommandOutput, String> {
    let len = u32::try_from(text.len()).unwrap_or(u32::MAX);
    Ok(SlashCommandOutput {
        text,
        sections: vec![SlashCommandOutputSection {
            range: zed::Range { start: 0, end: len },
            label: "Bookmark Quick Jump".to_string(),
        }],
    })
}

zed::register_extension!(BookmarkQuickJump);
