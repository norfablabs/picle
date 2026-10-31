"""Chat lifecycle through public command dispatch and scripted input."""

import io

import pytest
from pydantic import BaseModel, Field

from picle import App


def make_chat(monkeypatch, *, enter=True, exit=True, mounted=True):
    events = []
    context = {}

    class Commands(BaseModel):
        status: str = Field(None, json_schema_extra={"function": "status_command"})

        @staticmethod
        def status_command(**kwargs):
            assert context["ready"]
            events.append(("slash", {}))
            return "ready"

        @staticmethod
        def source_status():
            assert context["ready"]
            return ["ready"]

    class Chat(BaseModel):
        topic: str = Field("general", alias="subject")
        count: int = 1

        @staticmethod
        def run(message, **kwargs):
            if enter:
                assert context["ready"]
            events.append((message, kwargs))
            if message == "recover":
                raise ValueError("recoverable")
            if message == "stop":
                return None
            if message == "shutdown":
                return True
            return "reply"

        class PicleConfig:
            chat_shell = True
            chat_commands_model = Commands if mounted else None

    def on_enter(**kwargs):
        context["ready"] = True
        events.append(("enter", kwargs))

    def on_exit(**kwargs):
        context.clear()
        events.append(("exit", kwargs))

    if enter:
        monkeypatch.setattr(
            Chat, "chat_on_enter", staticmethod(on_enter), raising=False
        )
    if exit:
        monkeypatch.setattr(Chat, "chat_on_exit", staticmethod(on_exit), raising=False)

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    return app, Chat, events


def state(app):
    return app.shell, app.shells[:], app.prompt, app.is_chat, app.shell_defaults.copy()


@pytest.mark.parametrize(
    "ending",
    [
        "/exit",
        EOFError,
        KeyboardInterrupt,
        "stop",
        "shutdown",
        RuntimeError("read failed"),
    ],
)
@pytest.mark.parametrize("mounted", [True, False])
def test_chat_hooks_run_once(monkeypatch, capsys, ending, mounted):
    app, _, events = make_chat(monkeypatch, mounted=mounted)
    inputs = iter([ending])

    def read(*args, **kwargs):
        assert len(events) == 1 and events[0][0] == "enter"
        value = next(inputs)
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, type):
            raise value()
        return value

    monkeypatch.setattr(app, "_read_interactive_input", read)
    result = app.onecmd("chat")
    assert events[0][0] == "enter"
    assert events[-1] == ("exit", events[0][1])
    assert sum(name == "exit" for name, _ in events) == 1
    assert result is (True if ending in (KeyboardInterrupt, "shutdown") else None)
    if isinstance(ending, RuntimeError):
        assert "read failed" in capsys.readouterr().out


def test_chat_hooks_context_defaults_and_reopening(monkeypatch):
    app, _, events = make_chat(monkeypatch)
    for _ in range(2):
        app.shell_defaults.update(topic="shell", inherited="value")
        inputs = iter(["/status", "", "hello", "recover", "again", "/exit"])

        def read(*args, **kwargs):
            assert app.completedefault("", "status ", 7, 7) == ["ready "]
            return next(inputs)

        monkeypatch.setattr(app, "_read_interactive_input", read)
        app.onecmd("chat subject explicit count 2")
    assert [name for name, _ in events] == [
        "enter",
        "slash",
        "hello",
        "recover",
        "again",
        "exit",
    ] * 2
    for name, kwargs in events:
        if name != "slash":
            assert kwargs == {"topic": "explicit", "count": 2, "inherited": "value"}


@pytest.mark.parametrize("enter,exit", [(True, False), (False, True), (False, False)])
def test_optional_chat_hooks(monkeypatch, enter, exit):
    app, _, events = make_chat(monkeypatch, enter=enter, exit=exit)
    monkeypatch.setattr(app, "_read_interactive_input", lambda *a, **kw: "/exit")
    app.onecmd("chat")
    assert [name for name, _ in events] == (["enter"] if enter else []) + (
        ["exit"] if exit else []
    )


def test_validation_and_entry_failure_do_not_read(monkeypatch, capsys):
    app, chat, events = make_chat(monkeypatch)
    before = state(app)

    def unexpected_read(*args, **kwargs):
        pytest.fail("chat must not read input")

    monkeypatch.setattr(app, "_read_interactive_input", unexpected_read)
    app.onecmd("chat count invalid")
    assert events == []

    def fail(**kwargs):
        raise ValueError("entry failed")

    monkeypatch.setattr(chat, "chat_on_enter", staticmethod(fail))
    app.onecmd("chat")
    assert "entry failed" in capsys.readouterr().out
    assert events == []
    assert state(app) == before


@pytest.mark.parametrize("ending", ["shutdown", RuntimeError("original error")])
def test_exit_failure_uses_command_error_reporting(monkeypatch, capsys, ending):
    app, chat, _ = make_chat(monkeypatch)

    def fail(**kwargs):
        raise ValueError("exit failed")

    def read(*args, **kwargs):
        if isinstance(ending, Exception):
            raise ending
        return ending

    monkeypatch.setattr(chat, "chat_on_exit", staticmethod(fail))
    monkeypatch.setattr(app, "_read_interactive_input", read)
    assert app.onecmd("chat") is None
    output = capsys.readouterr().out
    assert "exit failed" in output
    if isinstance(ending, Exception):
        assert "original error" in output


def test_inherited_hooks_with_calling_subshell(monkeypatch):
    _, chat, events = make_chat(monkeypatch)

    class InheritedChat(chat):
        pass

    class Outer(BaseModel):
        chat: InheritedChat = None
        user: str = "alice"

        class PicleConfig:
            subshell = True
            prompt = "outer> "

    class Root(BaseModel):
        outer: Outer = None

    app = App(Root, stdout=io.StringIO())
    app.onecmd("outer")
    monkeypatch.setattr(app, "_read_interactive_input", lambda *a, **kw: "/exit")
    app.onecmd("chat")
    assert [name for name, _ in events] == ["enter", "exit"]
    assert events[0][1]["user"] == "alice"


def test_command_parent_hooks_are_not_used(monkeypatch):
    app, _, events = make_chat(monkeypatch, enter=False, exit=False)
    parent = app.shell if isinstance(app.shell, type) else type(app.shell)

    def unexpected_hook(**kwargs):
        pytest.fail("command parent hook must not run")

    monkeypatch.setattr(
        parent, "chat_on_enter", staticmethod(unexpected_hook), raising=False
    )
    monkeypatch.setattr(
        parent, "chat_on_exit", staticmethod(unexpected_hook), raising=False
    )
    monkeypatch.setattr(app, "_read_interactive_input", lambda *a, **kw: "/exit")
    app.onecmd("chat")
    assert events == []
