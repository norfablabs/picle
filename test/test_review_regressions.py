"""Regression cases from the parser and dispatch review."""

import io
from enum import Enum
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field, Json

from picle import App


@pytest.mark.parametrize("value", ["invalid", "0"])
def test_invalid_enum_does_not_execute(value):
    calls = []

    class Mode(str, Enum):
        safe = "safe"
        fast = "fast"

    class Command(BaseModel):
        mode: Mode = Mode.safe

        @staticmethod
        def run(**kwargs):
            calls.append(kwargs)

    class Root(BaseModel):
        command: Command = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    app.onecmd(f"command mode {value}")
    assert calls == []
    assert "validation error" in app.stdout.getvalue()


@pytest.mark.parametrize("value", ['{"x":1}', "[1,2]"])
def test_compact_json_preserves_following_argument(value):
    calls = []

    class Command(BaseModel):
        data: Json = None
        count: int = 1

        @staticmethod
        def run(**kwargs):
            calls.append(kwargs)

    class Root(BaseModel):
        command: Command = None

    app = App(Root, stdout=io.StringIO())
    app.onecmd(f"command data {value} count 2")
    assert calls == [{"data": value, "count": 2}]


@pytest.mark.parametrize("value,valid", [("invalid", False), ("0", False), ("2", True)])
def test_pipe_arguments_are_validated_against_pipe_model(value, valid):
    calls = []

    class Pipe(BaseModel):
        count: int = Field(None, ge=1)

        @staticmethod
        def run(previous, **kwargs):
            calls.append((previous, kwargs))
            return "done"

    class Source(BaseModel):
        @staticmethod
        def run(**kwargs):
            return "source"

        class PicleConfig:
            pipe = Pipe

    class Root(BaseModel):
        source: Source = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    app.onecmd(f"source | count {value}")
    assert calls == ([("source", {"count": 2})] if valid else [])
    if not valid:
        assert "validation error" in app.stdout.getvalue()


@pytest.mark.parametrize("navigation", ["exit", "top"])
def test_navigation_with_root_config_without_prompt(navigation):
    class Child(BaseModel):
        class PicleConfig:
            subshell = True

    class Root(BaseModel):
        child: Child = None

        class PicleConfig:
            history_file = None

    app = App(Root, stdout=io.StringIO())
    prompt = app.prompt
    app.onecmd("child")
    app.onecmd(navigation)
    assert len(app.shells) == 1
    assert app.shell is app.shells[0]
    assert app.prompt == prompt


@pytest.mark.usefixtures("scripted_chat")
def test_chat_end_is_rejected_and_exit_runs_hook_once(monkeypatch):
    exit_hook = Mock()

    class Chat(BaseModel):
        @staticmethod
        def run(message, **kwargs):
            return "reply"

        chat_on_exit = staticmethod(exit_hook)

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    read = Mock(side_effect=["/end", "/exit"])
    monkeypatch.setattr(app, "_read_interactive_input", read)
    assert app.onecmd("chat") is None
    assert read.call_count == 2
    assert "Use /exit" in app.stdout.getvalue()
    exit_hook.assert_called_once_with()


def test_end_completion_is_available_only_outside_chat():
    class Root(BaseModel):
        pass

    app = App(Root, stdout=io.StringIO())
    assert "end " in app.completenames("e", "e", 0, 1)
    app.is_chat = True
    assert "/end " not in app.completenames("/e", "/e", 0, 2)
    assert "/exit " in app.completenames("/e", "/e", 0, 2)
