# Chat Interface

The chat interface provides an interactive loop where a user sends messages
and receives responses, similar to chatting with an AI agent or LLM.

Enable it by setting `chat_shell = True` in a model's `PicleConfig` inner
class. When the user invokes that model without arguments PICLE enters the
chat loop and repeatedly prompts for input, passing each line as the first
positional argument to the model's `run` method.

Lines starting with `/` are dispatched to a dedicated command model
(`chat_commands_model`) instead of the chat function. `/exit` always exits
the loop and returns to the normal shell prompt.

## Basic example

```python
from pydantic import BaseModel, Field
from picle import App


class AgentModel(BaseModel):
    model: str = Field(None, description="LLM model name")

    @staticmethod
    def run(message, **kwargs):
        # Replace with your LLM / agent call
        return f"Assistant: I received '{message}'"

    class PicleConfig:
        chat_shell = True
        chat_prompt = "You> "
        chat_commands_model = None   # set to a model for /commands support


class Root(BaseModel):
    agent: AgentModel = Field(None, description="AI agent chat")
```

```
picle# agent
You> Hello!
Assistant: I received 'Hello!'
You> How are you?
Assistant: I received 'How are you?'
You> <Ctrl+D>
picle#
```

The loop continues until the user presses **Ctrl+D** (EOF) or types `/exit`.

For comprehensive chat app example refer to [sample chat app in PICLE test folder](https://github.com/dmulyalin/picle/blob/master/test/example_chat_app.py)

## Session hooks

Define optional synchronous `chat_on_enter(**kwargs)` and
`chat_on_exit(**kwargs)` methods on the chat command model, outside
`PicleConfig`, to manage application-owned context:

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

Entry runs once after validation and before the first input, so slash
commands and completion sources can use the initialized context. Exit runs
once when the chat loop ends, including on `/exit`, EOF,
Ctrl+C, handler termination, or an escaping error. Errors handled inside the
message loop leave the session open. Reopening chat runs the hooks again.

Both hooks receive the message handler's resolved keyword arguments, without
its positional message: shell defaults, then command defaults, then explicit
arguments. Existing argument names and alias handling apply. Return values
are ignored. Either hook can be omitted; normal class inheritance works.
Hooks are looked up on the chat command model, with no fallback to command
parents or the mounted slash-command model.

Validation failure runs neither hook. If entry raises, PICLE reports the
error without reading input or calling exit; the application is responsible
for cleaning up partial initialization. Exit errors are reported through the
normal command exception handler and override any pending chat return value.

## PicleConfig options

| Option | Default | Description |
|--------|---------|-------------|
| `chat_shell` | `False` | Set to `True` to enable chat loop when the model is invoked. |
| `chat_prompt` | `"> "` | Prompt string shown before each user input. |
| `chat_response_style` | `None` | Rich markup style applied to responses (e.g. `"green"`, `"bold cyan"`). Only used when Rich is installed. |
| `chat_response_prefix` | `""` | Text prepended to each response (e.g. `"AI> "`). |
| `chat_commands_model` | `None` | Pydantic model class whose fields are available as `/commands` inside the chat loop. |

## Slash commands

Lines that start with `/` are dispatched to `chat_commands_model` instead
of the chat function. This lets users run sub-commands without leaving
the chat:

```
You> tell me a joke
Assistant: Why did the programmer quit? Because he didn't get arrays.
You> /show usage
1234; 1234; 1234
You> /exit
picle#
```

`/exit` always exits the chat loop. `chat_commands_model` must be provided
for any other slash commands to work.

```python
class ShowCommands(BaseModel):
    usage: Any = Field(None, json_schema_extra={"function": "show_usage"})

    @staticmethod
    def show_usage():
        return "1234; 1234; 1234"


class AgentModel(BaseModel):
    model: str = Field(None, description="LLM model name")

    @staticmethod
    def run(message, **kwargs):
        return f"Echo: {message}"

    class PicleConfig:
        chat_shell = True
        chat_commands_model = ShowCommands
```

## Rich styled responses

When Rich is installed and `use_rich` is enabled, you can style agent
responses to visually distinguish them from user input.

```python
class AgentModel(BaseModel):
    @staticmethod
    def run(message, **kwargs):
        return f"I received: {message}"

    class PicleConfig:
        chat_shell = True
        chat_prompt = "You> "
        chat_response_style = "green"
        chat_response_prefix = "AI> "
```

```
You> Hello
AI> I received: Hello       <-- printed in green when Rich is available
You>
```

Any Rich console markup style is supported: `"bold cyan"`, `"italic yellow"`,
`"dim"`, etc.

## Streaming responses

If `run` returns a generator (or any iterator), the chat loop writes each
chunk to stdout as it arrives instead of waiting for the full response.

```python
class StreamingAgent(BaseModel):
    @staticmethod
    def run(message, **kwargs):
        def stream():
            for token in message.split():
                yield token + " "
        return stream()

    class PicleConfig:
        chat_shell = True
```

This is useful for LLM token streaming and other incremental output flows.
Pressing **Ctrl+C** while streaming cancels the current response and returns
to the chat prompt.

## Exiting the chat from the run function

The chat loop normally continues until the user presses **Ctrl+D** or types
`/exit`. The `run` method can also control loop exit:

- **`return None`** — exits the chat loop and returns to the shell prompt.
- **`return True`** — exits the chat loop **and** terminates the current shell.

**Ctrl+C** behavior depends on context:

- During streaming output: cancels the current response and returns to the chat prompt.
- At the chat prompt (waiting for input): exits the chat loop and terminates the current shell.

```python
class AgentModel(BaseModel):
    @staticmethod
    def run(message, **kwargs):
        if message.lower() == "bye":
            return None      # exit chat, return to shell
        if message.lower() == "shutdown":
            return True      # exit chat and terminate shell
        return f"Echo: {message}"

    class PicleConfig:
        chat_shell = True
```
