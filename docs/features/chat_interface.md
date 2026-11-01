# Chat Interface

Chat mode lets users exchange messages with an agent while running commands
without leaving the conversation. The message editor stays visible while a
response is being prepared. Progress, status and approval requests appear
above it.

## Basic example

Set `chat_shell = True` on the chat model and define `run()` to handle each
submitted message:

```python
from pydantic import BaseModel, Field
from picle import App


class AgentModel(BaseModel):
    @staticmethod
    def run(message, **kwargs):
        return f"I received: {message}"

    class PicleConfig:
        chat_shell = True
        chat_prompt = "You> "
        chat_response_prefix = "AI> "


class Root(BaseModel):
    agent: AgentModel = Field(None, description="Chat with the agent")


App(Root).start()
```

Enter `agent` at the shell prompt to start chatting. Type `/exit` on a single
line to return to the parent shell.

For a working example, run this command from the repository root:

```shell
poetry run python -m test.example_chat_app
```

Then enter `chat session_id demo user alice`. Try `work` for progress updates,
`fail` for an example error, or `approve` for an approval request.

## Writing messages

| Key | Action |
|-----|--------|
| Enter | Send the message. If a completion is selected, accept it first. |
| Alt+Enter | Insert a newline by default. |
| Tab | Complete a slash command. |
| Arrow keys | Move within the message; Up/Down also recall earlier chat input. |

Paste or type several lines, edit them, then press Enter to send the complete
message. Indentation and surrounding whitespace are preserved. Pressing Enter
on empty or whitespace-only input does nothing.

The editor shows five text rows by default, wraps long lines and scrolls as
you move through longer messages. Set `chat_input_height` to change its height;
it shrinks to fit smaller terminals.

Use the terminal's scroll controls to review earlier messages and responses.
Chat input history is separate from shell command history and is available
across chat sessions until the app closes. Chat input is not saved to disk.

While a response is being prepared, you can compose the next message, but
must wait for the current operation to finish before sending it. **Ctrl+C
and Ctrl+D do not cancel a running operation or close a busy chat.**

## PicleConfig options

Set these options on the chat model, except `chat_newline_keys`, which belongs
on the root model and applies to all chat sessions.

| Option | Default | Description |
|--------|---------|-------------|
| `chat_shell` | `False` | Enable chat mode for this model. |
| `chat_prompt` | `"> "` | Prefix shown with submitted messages. |
| `chat_input_height` | `5` | Visible text rows, excluding separator lines. Uses at least one row and shrinks to fit the terminal. |
| `chat_newline_keys` | `"alt+enter"` | Newline shortcut for all chats. Accepts `"alt+enter"`, a key name such as `"c-j"` for Ctrl+J, or a tuple of key names for a sequence. |
| `chat_response_style` | `None` | Response style such as `"green"` or `"bold cyan"`. Requires Rich and `use_rich = True`. |
| `chat_response_prefix` | `""` | Prefix shown before responses, such as `"AI> "`. |
| `chat_commands_model` | `None` | Model defining custom slash commands. |

For example, to show eight input rows and green responses:

```python
class PicleConfig:
    chat_shell = True
    chat_input_height = 8
    chat_response_prefix = "AI> "
    chat_response_style = "green"
```

## Changing the newline shortcut

Configure `chat_newline_keys` on the root model:

```python
class Root(BaseModel):
    agent: AgentModel = None

    class PicleConfig:
        chat_newline_keys = "c-j"  # Ctrl+J; default is "alt+enter"
```

The new shortcut replaces Alt+Enter. To use Shift+Enter, configure `"c-j"`
as above and map Shift+Enter to a line feed in your terminal. In VS Code,
add this entry to your user `keybindings.json`:

```json
{
    "key": "shift+enter",
    "command": "workbench.action.terminal.sendSequence",
    "args": {"text": "\u000a"},
    "when": "terminalFocus"
}
```

## Slash commands

A single-line message beginning with `/` runs a command instead of sending a
message to the agent. Define custom commands with `chat_commands_model`:

```python
from typing import Any


class ChatCommands(BaseModel):
    usage: Any = Field(None, json_schema_extra={"function": "show_usage"})

    @staticmethod
    def show_usage():
        return "1234 tokens used"


class AgentModel(BaseModel):
    @staticmethod
    def run(message, **kwargs):
        return f"Echo: {message}"

    class PicleConfig:
        chat_shell = True
        chat_commands_model = ChatCommands
```

In this example, `/usage` displays the custom usage report. It is not a
built-in command. Type `/exit` to leave chat. Commands that ask for additional
input may temporarily
hide the message editor until that input is complete.

A message containing any line break is always sent to the agent, even if it
starts with `/` or has only a trailing newline. Nested chats and shell
navigation from slash commands are not supported.

## Progress, status and approvals

Add a named `chat` parameter to `run()` to show progress or ask for approval:

```python
class AgentModel(BaseModel):
    @staticmethod
    def run(message, chat, **kwargs):
        chat.set_footer("Model: local | Session: demo")
        chat.set_status("Working...", spinner=True)
        chat.write("Checking the request")
        if not chat.approve("Allow this action?"):
            return "Action denied"
        chat.write("Action allowed")
        return f"Completed: {message}"

    class PicleConfig:
        chat_shell = True
```

| Method | Use |
|--------|-----|
| `chat.write(text)` | Add a plain-text progress message above the editor. Embedded newlines are preserved; a final newline is optional. |
| `chat.set_status(text="", spinner=False)` | Replace the temporary status line. Set `spinner=True` to show activity, or call with no text to clear it. Status also clears when the operation finishes. |
| `chat.set_footer(text="")` | Replace the single-line footer below the editor. It stays between messages, including after an error. Call with no text to hide it. Long text is clipped to the available width. |
| `chat.approve(prompt)` | Ask the user to press **Y** to Allow or **N** to Deny. Returns `True` or `False`. |

An approval waits for the user's choice before continuing. While it is
pending, keyboard input answers the approval; afterward, the message editor
is active again. Ask for one approval at a time. If chat closes unexpectedly,
a pending approval is denied.

Call these methods directly from `run()`, not from hooks or background
callbacks. Declare `chat` explicitly: `**kwargs` alone does not receive it.
Do not use `chat` as the name of a user-supplied command argument.

Return the final answer normally; do not also send it with `chat.write()`.
Response prefixes, styles and outputters continue to apply. Return a complete
answer rather than a generator or iterator. Use `chat.write()` for progress
instead of `print()`, terminal logs or a separate live display.

## Session hooks

Use `chat_on_enter()` to initialize context before the first message and
`chat_on_exit()` to clean it up when chat ends. Define them on the chat model,
not inside `PicleConfig`:

```python
context = {}


class AgentModel(BaseModel):
    topic: str = "general"

    @staticmethod
    def chat_on_enter(**kwargs):
        context["topic"] = kwargs["topic"]

    @staticmethod
    def chat_on_exit(**kwargs):
        context.clear()

    @staticmethod
    def run(message, **kwargs):
        return f"{context['topic']}: {message}"

    class PicleConfig:
        chat_shell = True
```

Each hook runs once per session. Either may be omitted. Both receive command
arguments and defaults, with explicit arguments taking precedence. They do
not receive the `chat` object, and their return values are ignored.

If command validation fails, neither hook runs. If entry fails, chat does
not open and exit is not called; clean up any partially initialized context
in the entry hook. Exit errors are reported and can prevent a requested app
termination from taking effect.

## Ending a session

- `/exit` leaves chat and returns to the parent shell.
- Ctrl+D on an empty editor ends chat while idle.
- Ctrl+C while idle ends chat and terminates the app.
- Returning `None` from `run()` ends chat.
- Returning `True` from `run()` ends chat and terminates the app.

After Ctrl+D or a handler ending chat, a configured slash-command shell may
remain active. Use `exit` to return to its parent shell.

Handler errors are displayed so the user can try another message. The exit
hook runs when the session ends, including after an error that closes chat.
