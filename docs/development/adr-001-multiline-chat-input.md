# ADR-001: Editable multiline chat input

Status: Accepted; implemented.

Date: 2026-11-01

## Context

Chat users need to compose, paste and edit messages spanning several lines,
then submit the complete buffer as one message. Enter should submit rather
than insert a newline.

PICLE already uses a persistent `prompt_toolkit.PromptSession` for interactive
input. Rich renders responses and remains optional. The installed
prompt-toolkit 3.0.52 supports multiline editing and a frame around the input.
Reusing this backend avoids introducing a second terminal input system.

Two existing behaviors need explicit handling: `_run_chat_shell()` strips
the entire message, and `_PicleHistory` persists one physical line per entry.
Multiline messages should retain indentation and should not reload as several
independent shell history entries.

## Decision

Use a fixed-height multiline editor with top and bottom separator lines and vertical scrolling for
every chat session. Chat models continue to enable chat through the existing
setting:

```python
class PicleConfig:
    chat_shell = True
```

Do not add a `chat_multiline` setting or a separate single-line chat mode.
Use prompt-toolkit's `TextArea` inside a small non-full-screen application
layout without side borders. Keep the visible editor height bounded while allowing the message
to grow beyond it; scroll with the cursor and show a vertical scrollbar.
Omit the keyboard-controls hint to save terminal space. Rich continues to
render responses outside the active editor.

| Action | Behavior |
|--------|----------|
| Enter | Submit the complete buffer as one message. |
| Alt+Enter / Escape, then Enter | Insert a newline by default. |
| Arrow keys | Move within the editable buffer, scrolling when needed. |
| Bracketed multiline paste | Insert all pasted text without submitting it. |

If a completion is active, Enter accepts it before submitting the message,
preserving the existing completion interaction. Configure the app-wide newline
sequence using `chat_newline_keys` in the root model's `PicleConfig`. Its default
is the user-facing name `"alt+enter"`, translated internally to
`("escape", "enter")`. A key name such as `"c-j"` replaces the default with
Ctrl+J; a terminal mapping can then send that sequence for Shift+Enter.
The chat documentation provides the VS Code mapping.

Preserve the original message buffer for the handler. Ignore whitespace-only
input. Check for line breaks in the original buffer before stripping whitespace
for slash-command parsing. Only single-line input beginning with `/` is
dispatched as a command; a multiline buffer remains one message even when a
line begins with `/`. This also applies to a buffer with a trailing newline.

Keep all chat input in separate in-memory history for the app instance.
Do not mix chat messages with shell commands or persist them to the shell's
history file. Preserve the existing shell history file format.

## Alternatives considered

- **Rich prompts:** useful for formatted prompts, but do not provide the
  editable multiline buffer required here. Retain Rich for response output.
- **Default prompt-toolkit multiline bindings:** Enter inserts a newline and
  Alt+Enter submits. Use Enter to submit and an app-configurable newline
  sequence, defaulting to Alt+Enter.
- **Expanding framed prompt:** needs less layout work but grows with the
  message. Select a fixed-height text area to keep the visible editor bounded.
- **Opt-in multiline setting:** preserves the old chat editor but adds a
  second input mode to configure and maintain. Use multiline input for all chat.
- **New persistent history format:** could retain complete multiline entries
  across runs, but adds migration and compatibility work beyond this feature.

## Implementation outline

1. Keep the editor and chat loop in `ChatShell` in `picle/chat.py`.
   `App._run_chat_shell()` delegates to the single persistent `ChatShell.run()`
   application. Normal shell input remains in `App._read_interactive_input()`.
   Use a
   prompt-toolkit `TextArea`, top and bottom separator lines,
   scrollbar in a non-full-screen layout. Reuse existing
   completion adapter and a separate in-memory chat history. Keep the normal shell's persistent
   `PromptSession` and `load-terminal` input path unchanged.
2. Add submit and newline bindings local to the chat editor, including active
   completion handling. Ensure the editor releases terminal control on normal
   completion and exceptions. Avoid using `self.is_chat` alone to select the
   reader, since slash commands can also request ordinary field input.
3. Use `ChatShell.run()` to preserve multiline message whitespace
   and apply the single-line slash-command rule. Keep lifecycle hooks,
   response outputters and existing idle Ctrl+C and EOF behavior.
4. Use a separate `InMemoryHistory` for chat input, retaining it across chat
   sessions in the same app instance. Keep ordinary shell input and
   `load-terminal` collection unchanged.
5. Document the editor, controls, command routing and history limitation in
   the chat interface page, and add a changelog entry when implemented.

## Consequences

No new dependency or full-screen application is needed. Every existing chat
model receives the new editor automatically. Ordinary shell input remains
unchanged.

Custom bindings and editor layout must be tested together with completion
and paste handling. Multiline messages will not be available in history after
restarting PICLE. Persistent multiline history can be considered separately.

## Verification

- Use real prompt-toolkit pipe input with `DummyOutput` to verify submission,
  newline insertion, cross-line edits, bracketed paste and completion. Assert
  that ordinary shell reads retain their original settings afterward.
- Use public `App.onecmd()` tests to verify one handler call per multiline
  buffer, preserved whitespace, slash-command routing and hooks running once
  per session. Exercise history save and reload to ensure multiline entries
  cannot split into shell commands.
- Manually verify Windows VS Code terminal behavior: editing previous lines,
  wrapping, fixed viewport height, scrolling through long messages, terminal
  resizing, paste, completion, submission and return to the shell.
- Run `poetry run pytest -q`, Black checks on changed Python files, and a
  strict MkDocs build targeting a temporary directory.

## Implementation detail

The viewport defaults to five text rows. The chat model's
`PicleConfig.chat_input_height` configures its height, excluding separator
lines. Reduce it to fit the available terminal height, with a minimum of one row.

## References

- [Prompt-toolkit prompts, multiline input and frames](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/asking_for_input.html)
- [Prompt-toolkit key bindings and terminal constraints](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/advanced_topics/key_bindings.html)
- [Prompt-toolkit application layouts and widgets](https://python-prompt-toolkit.readthedocs.io/en/stable/pages/full_screen_apps.html)
- [Rich prompts](https://rich.readthedocs.io/en/latest/prompt.html)

## Persistent layout extension

Keep one prompt-toolkit application alive during each chat session. Permanent
output goes to terminal scrollback; status, approval and input sections share
one renderer below it. Handlers run in a worker thread. Input remains editable
while busy, but submission and Ctrl+C/Ctrl+D termination are disabled until the
operation finishes. No queued or overlapping operations are allowed.

Expose `ChatSession.write(text)`, `set_status(text="", spinner=False)`, and
`approve(prompt) -> bool`. Inject the session only into the active handler
when it explicitly names `chat`; hooks receive command arguments only. Handler
updates are scheduled onto an ordered async UI queue. Additional callback
threads and concurrent approval requests are outside the supported scope.
The status row uses prompt-toolkit refreshes for animation. Approvals focus an
Allow/Deny section and block the worker, not the UI. Teardown denies pending
approvals and clears the chat flag. Hooks do not write session progress, so
there is no post-UI output flush. Do not snapshot or restore shell state:
`/exit` uses normal shell exit handling; EOF, errors and handler termination
may leave the slash-command model mounted. Nested chats and shell navigation
through slash commands are unsupported; custom slash commands remain available.

Streaming responses are removed. Handlers return complete answers, rendered
once using the existing outputter path. Arbitrary print/log capture, Rich Live,
cooperative cancellation and transcript navigation remain outside this scope.

`ChatSession.set_footer(text="")` replaces an optional row below
the bottom separator. It persists between messages and handler errors until
replaced or cleared, and resets when the session ends. Long content is clipped
without wrapping; a visible footer reduces the editor's available height by
one row. It uses the existing event queue and requires no additional setting.

`write()` accepts plain strings. Footers accept strings and prompt-toolkit
formatted text; status accepts plain strings. Layout widgets and Rich objects
are outside the session interface.
