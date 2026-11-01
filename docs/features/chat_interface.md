# Chat Interface

Use chat mode to exchange messages with an agent and run commands without
leaving the conversation. The message editor stays visible while a
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
`fail` for an example error, `approve` for an approval request, or `rich`
for styled text and a table (requires Rich).

## Writing messages

| Key | Action |
|-----|--------|
| Enter | Send the message. If a completion is selected, accept it first. |
| Alt+Enter | Insert a newline by default. |
| Tab | Complete a slash command. |
| Arrow keys | Move within the message; Up/Down also recall earlier chat input. |

Paste or type several lines, edit them, then press Enter to send the complete
message. Spaces, tabs and line breaks are kept as entered. Pressing Enter
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
input may temporarily hide the message editor until you finish answering.

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
        chat.set_status("Thinking", spinner=True, elapsed=True)
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
| `chat.write(text)` | Add a progress message above the editor. Accepts plain strings or Rich renderables. Embedded newlines are preserved; a final newline is optional. |
| `chat.set_status(text="", spinner=False, elapsed=False)` | Replace the temporary status line. Use `spinner=True` for activity and `elapsed=True` for elapsed minutes and seconds. Replacing the status resets the timer. Call with no text to clear it; status also clears when the operation finishes. |
| `chat.set_footer(text="")` | Replace the single-line footer below the editor. Accepts plain strings or prompt-toolkit formatted text. It stays between messages, including after an error. Call with no text to hide it. Long text is clipped to the available width. |
| `chat.approve(prompt)` | Ask the user to press **Y** to Allow or **N** to Deny. Returns `True` or `False`. |

Use the following examples inside `run(message, chat, **kwargs)`. Plain
strings are displayed as written. For styled output, use Rich objects with
`write()` or prompt-toolkit formatted text with `set_footer()`.

=== "Write"

    Add progress messages above the editor. Each call adds a new entry;
    embedded newlines are preserved.

    **Plain text**

    ```python
    chat.write("Checking the request")
    chat.write("Step 1 complete\nStarting step 2")
    ```

    **Styled text with Rich**

    With Rich installed and `use_rich = True`, you can also write styled text,
    tables and panels:

    ```python
    from rich.text import Text
    from rich.table import Table

    chat.write(Text("Request accepted", style="bold green"))

    table = Table("Step", "Result")
    table.add_row("Check request", "Passed")
    chat.write(table)
    ```

    Without Rich output enabled, objects are shown as their plain string
    representation. Return the final answer normally instead of also writing
    it here.

=== "Status"

    Show a temporary message while work is in progress:

    ```python
    chat.set_status("Checking the request")
    ```

    Show cycling dots after the text, followed by elapsed time, such as
    `Thinking...  00:12`:

    ```python
    chat.set_status("Thinking", spinner=True, elapsed=True)
    # Perform your operation here.
    ```

    Replace or clear the status:

    ```python
    chat.set_status("Finishing...")  # replaces the previous status
    chat.set_status()               # clears it
    ```

    Replacing the status resets its timer. Status clears automatically when
    the operation finishes. Status text accepts plain strings.

=== "Footer"

    Show session information below the editor. Setting a footer replaces its
    previous content; it stays between messages until replaced or cleared.

    **Plain text**

    ```python
    chat.set_footer("Model: local | Session: demo")
    ```

    **Prompt-toolkit formatted text**

    ```python
    from prompt_toolkit.formatted_text import HTML

    chat.set_footer(HTML("<b>Model:</b> local | <ansigreen>Connected</ansigreen>"))
    ```

    Hide the footer:

    ```python
    chat.set_footer()
    ```

    The footer occupies one row; long content is clipped. It resets when the
    chat session ends.

For more footer styles, you can also use prompt-toolkit `ANSI`,
`FormattedText`, styled text fragments, or a function that returns formatted
text. The footer stays one row high regardless of the content.

### Supported content types

| Method | Plain strings | Prompt-toolkit formatted text | Rich objects |
|--------|---------------|-------------------------------|--------------|
| `chat.write()` | Yes | **Not supported** | Yes, when Rich is installed and `use_rich = True`; otherwise shown as a string |
| `chat.set_footer()` | Yes | Yes: `HTML`, `ANSI`, `FormattedText`, styled fragments and callables | **Not supported**, including Rich `Text` |
| `chat.set_status()` | Yes | **Not supported** | **Not supported**, including Rich `Text` and Rich spinners |

For a styled footer, use prompt-toolkit `HTML` or `FormattedText`. For status
animation and timing, use the `spinner=True` and `elapsed=True` arguments.
Rich renderables such as `Text`, `Panel` and `Table` can be passed to
`write()`, but not to status or footer. `Console`, `Live` and prompt-toolkit
layout widgets are not supported.

Strings are always plain text: `"[green]Ready[/green]"` and `"<b>Ready</b>"`
are displayed literally rather than interpreted as markup.

### Asking for approval

Call `chat.approve("Allow this action?")` before an action that needs the
user's permission. Pressing **Y** returns `True`; pressing **N** returns
`False`. Your handler waits for that choice before continuing.

While the request is visible, the keyboard answers it. After the choice,
you can edit messages again. Ask for one approval at a time. If chat closes
unexpectedly, the request is denied.

Use these methods only inside `run()`. Add `chat` to its parameter list;
`**kwargs` alone does not receive it. Hooks and background callbacks cannot
use the session methods. Keep the name `chat` for this parameter rather than
using it for a command argument.

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

The entry hook runs once before the first message, and the exit hook runs
once when the session ends. You can define either hook or both. Both receive command
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
