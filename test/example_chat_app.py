"""
Example chat shell app for PICLE with deterministic mock responses.

Run:
    python example_chat_app.py

Inside chat mode:
- Type normal text to receive a mock assistant response.
- Use slash commands:
  - /show usage
  - /show status
  - /set_model <name>
  - /reset
  - /exit
"""

import time
from typing import Any

from pydantic import BaseModel, Field, StrictStr

from picle import App


class MockChatState:
    """In-memory state for the mock chat responder."""

    model_name = "mock-1"
    turn = 0
    history: list[str] = []

    @classmethod
    def reset(cls) -> None:
        cls.model_name = "mock-1"
        cls.turn = 0
        cls.history = []


class ChatShowCommands(BaseModel):
    """Read-only slash commands for usage and runtime state."""

    usage: Any = Field(
        None,
        description="Show available slash commands",
        json_schema_extra={"function": "show_usage"},
    )
    status: Any = Field(
        None,
        description="Show current mock chat state",
        json_schema_extra={"function": "show_status"},
    )

    @staticmethod
    def show_usage() -> str:
        return "Current usage  1234 tokens."

    @staticmethod
    def show_status() -> str:
        return (
            f"model={MockChatState.model_name}; "
            f"turns={MockChatState.turn}; "
            f"messages={len(MockChatState.history)}"
        )


class ChatCommands(BaseModel):
    """Slash command model mounted during chat mode."""

    show: ChatShowCommands = Field(None, description="Show command helpers")
    set_model: StrictStr = Field(
        None,
        description="Switch active mock model",
        json_schema_extra={"function": "set_model_name"},
    )
    reset: Any = Field(
        None,
        description="Reset mock chat state",
        json_schema_extra={"function": "reset_state", "presence": True},
    )

    @staticmethod
    def set_model_name(set_model: str, **kwargs) -> str:
        MockChatState.model_name = set_model
        return f"mock model switched to '{set_model}'"

    @staticmethod
    def reset_state(**kwargs) -> str:
        MockChatState.reset()
        return "mock chat state reset"


class MockChatAgent(BaseModel):
    """Mock chat model that demonstrates message handling and streaming."""

    session_id: StrictStr = Field(None, description="Chat session identifier")
    user: StrictStr = Field("guest", description="Display name for responses")

    @staticmethod
    def run(message: str, chat=None, **kwargs):
        normalized = message.strip()
        if normalized.lower() == "bye":
            return None
        if normalized.lower() == "rich":
            try:
                from rich.text import Text
                from rich.table import Table
            except ImportError:
                return "Install Rich to try this example: poetry install -E full"
            chat.write(Text("Rich progress message", style="bold green"))
            table = Table("Step", "Status")
            table.add_row("Example", "Complete")
            chat.write(table)
            return "Rich output complete"
        if normalized.lower() in {"work", "fail"}:
            chat.set_status("Working...", spinner=True, elapsed=True)
            chat.write("Starting operation")
            time.sleep(1)
            if normalized.lower() == "fail":
                raise ValueError("Example operation failed")
            chat.write("Operation completed")
            return "Done"
        if normalized.lower() == "approve":
            return "Allowed" if chat.approve("Allow the example action?") else "Denied"

        MockChatState.turn += 1
        MockChatState.history.append(normalized)

        session_id = kwargs.get("session_id", "no-session")
        user = kwargs.get("user", "guest")

        if normalized.lower().startswith("stream "):
            payload = normalized[7:]

            return (
                f"[model={MockChatState.model_name}] "
                f"[turn={MockChatState.turn}] "
                f"[session={session_id}] {user}: {payload.upper()}"
            )

        return (
            f"[model={MockChatState.model_name}] "
            f"[turn={MockChatState.turn}] "
            f"[session={session_id}] "
            f"{user}: {normalized[::-1]}"
        )

    class PicleConfig:
        chat_shell = True
        chat_prompt = "You> "
        chat_response_prefix = "AI> "
        chat_response_style = "green"
        chat_command_prefix = "/"
        chat_commands_model = ChatCommands


class Root(BaseModel):
    """Root model for the example shell."""

    chat: MockChatAgent = Field(None, description="Open mock chat shell")

    class PicleConfig:
        prompt = "example-chat#"
        intro = "Example chat shell"
        newline = "\r\n"
        use_rich = True


if __name__ == "__main__":
    App(Root).start()
