"""Persistent chat behavior through public command dispatch and real UI input."""

import io
import threading
from unittest.mock import Mock

import pytest
from pydantic import BaseModel
from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from picle import App, ChatSession


def test_progress_hooks_busy_editing_and_closure(monkeypatch):
    calls = []
    sessions = []
    started = threading.Event()
    release = threading.Event()

    class Chat(BaseModel):
        @staticmethod
        def chat_on_enter(**kwargs):
            assert "chat" not in kwargs

        @staticmethod
        def run(message, chat, **kwargs):
            if not sessions:
                sessions.append(chat)
            assert chat is sessions[0]
            calls.append(message)
            if len(calls) == 2:
                return None
            chat.write("first")
            chat.write("second\nline")
            chat.set_status("Working", spinner=True)
            started.set()
            assert release.wait(timeout=5)
            return "answer"

        @staticmethod
        def chat_on_exit(**kwargs):
            assert "chat" not in kwargs

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    before = (app.shell, app.shells[:], app.prompt, app.is_chat)
    phases = []
    applications = []

    with create_pipe_input() as source:

        def rendered(ui):
            if ui.is_done:
                return
            if not phases:
                source.send_text("hello\r")
                phases.append("sent")
            elif phases[-1] == "sent" and started.is_set() and app._chat_shell._status:
                assert app._chat_shell._busy
                assert ui.current_buffer.read_only() is False
                source.send_text("draft\r\x03\x04")
                phases.append("editing")
            elif phases[-1] == "editing" and ui.current_buffer.text == "draft":
                assert calls == ["hello"]
                assert app._chat_shell._busy
                release.set()
                phases.append("released")
            elif phases[-1] == "released" and not app._chat_shell._busy:
                assert app._chat_shell._status == ""
                source.send_text("\r")
                phases.append("submitted draft")

        def application(**kwargs):
            ui = Application(**kwargs, after_render=rendered)
            applications.append(ui)
            return ui

        monkeypatch.setattr("picle.chat.Application", application)
        with create_app_session(input=source, output=DummyOutput()):
            assert app.onecmd("chat") is None

    assert len(applications) == 1
    assert calls == ["hello", "draft"]
    output = app.stdout.getvalue()
    assert output.index("first") < output.index("second\nline") < output.index("answer")
    assert output.count("answer") == 1
    assert "Working" not in output
    assert (app.shell, app.shells, app.prompt, app.is_chat) == before
    sessions[0].write("late")
    sessions[0].set_status("late")
    assert sessions[0].approve("late?") is False
    assert app.stdout.getvalue() == output
    assert sessions[0]._events.empty()


@pytest.mark.parametrize("choice,expected", [("y", True), ("n", False)])
def test_handler_approval_keeps_ui_alive(monkeypatch, choice, expected):
    decisions = []

    class Chat(BaseModel):
        @staticmethod
        def run(message, chat):
            decisions.append(chat.approve("Allow this action?"))
            return "approved" if decisions[-1] else "denied"

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    phases = []
    with create_pipe_input() as source:

        def rendered(ui):
            if ui.is_done:
                return
            if not phases:
                source.send_text("request\r")
                phases.append("sent")
            elif phases[-1] == "sent" and app._chat_shell._approval:
                assert app._chat_shell._busy
                source.send_text(choice)
                phases.append("decided")
            elif phases[-1] == "decided" and not app._chat_shell._busy:
                assert app._chat_shell._approval is None
                source.send_text("/exit\r")
                phases.append("exit")

        monkeypatch.setattr(
            "picle.chat.Application",
            lambda **kw: Application(**kw, after_render=rendered),
        )
        with create_app_session(input=source, output=DummyOutput()):
            app.onecmd("chat")
    assert decisions == [expected]
    assert ("approved" if expected else "denied") in app.stdout.getvalue()


def test_closed_session_ignores_callbacks():
    session = ChatSession()
    session._closed = True
    session.write("late")
    session.set_status("late", spinner=True)
    assert session.approve("late?") is False
    assert session._events.empty()


@pytest.mark.usefixtures("scripted_chat")
def test_immediate_exit_calls_hooks_without_session_injection(monkeypatch):
    hooks = []

    class Chat(BaseModel):
        @staticmethod
        def chat_on_enter(**kwargs):
            hooks.append(("entry", kwargs))

        @staticmethod
        def chat_on_exit(**kwargs):
            hooks.append(("exit", kwargs))

        @staticmethod
        def run(message):
            pytest.fail("handler must not run")

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    monkeypatch.setattr(app, "_read_interactive_input", lambda *a, **kw: "/exit")
    app.onecmd("chat")
    assert hooks == [("entry", {}), ("exit", {})]


@pytest.mark.parametrize("failure", ["exception", "iterator"])
@pytest.mark.usefixtures("scripted_chat")
def test_response_error_recovers_and_outputter_runs_once(monkeypatch, failure):
    class Chat(BaseModel):
        @staticmethod
        def run(message, chat):
            if message == "fail":
                chat.set_status("busy", spinner=True)
                if failure == "iterator":
                    return iter(["must not stream"])
                raise ValueError("operation failed")
            return ("done", lambda value, prefix: prefix + value, {"prefix": "render:"})

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    inputs = iter(["fail", "okay", "/exit"])
    monkeypatch.setattr(app, "_read_interactive_input", lambda *a, **kw: next(inputs))
    app.onecmd("chat")
    output = app.stdout.getvalue()
    assert (
        "operation failed" if failure == "exception" else "streaming is not supported"
    ) in output
    assert output.count("render:done") == 1
    assert "must not stream" not in output
    assert app._chat_shell._status == ""


def test_teardown_denies_pending_approval(monkeypatch, capsys):
    decisions = []
    sessions = []

    class Chat(BaseModel):
        @staticmethod
        def run(message, chat):
            sessions.append(chat)
            decisions.append(chat.approve("Allow?"))
            return "finished"

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    phases = []
    with create_pipe_input() as source:

        def rendered(ui):
            if ui.is_done:
                return
            if not phases:
                source.send_text("request\r")
                phases.append("sent")
            elif app._chat_shell._approval:
                ui.exit(exception=RuntimeError("forced teardown"))

        monkeypatch.setattr(
            "picle.chat.Application",
            lambda **kw: Application(**kw, after_render=rendered),
        )
        with create_app_session(input=source, output=DummyOutput()):
            app.onecmd("chat")
    assert decisions == [False]
    assert sessions[0]._closed
    assert app.is_chat is False
    assert "forced teardown" in capsys.readouterr().out


@pytest.mark.usefixtures("scripted_chat")
def test_eof_leaves_slash_model_mounted_without_chat_mode(monkeypatch):
    class Commands(BaseModel):
        pass

    class Chat(BaseModel):
        @staticmethod
        def run(message):
            return "reply"

        class PicleConfig:
            chat_shell = True
            chat_commands_model = Commands

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    monkeypatch.setattr(app, "_read_interactive_input", Mock(side_effect=EOFError))
    app.onecmd("chat")
    assert app.shell is Commands
    assert app.shells[-1] is Commands
    assert app.is_chat is False
    assert app._chat_shell.session._closed


def test_footer_replaces_persists_and_clears_without_scrollback(monkeypatch):
    from prompt_toolkit.data_structures import Size

    sessions = []

    class Chat(BaseModel):
        @staticmethod
        def run(message, chat):
            sessions.append(chat)
            if message == "set":
                chat.set_footer("first " * 30)
            elif message == "replace":
                chat.set_footer("second")
            elif message == "fail":
                raise ValueError("operation failed")
            else:
                chat.set_footer()
            return "done"

        class PicleConfig:
            chat_shell = True

    class Root(BaseModel):
        chat: Chat = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    output = DummyOutput()
    monkeypatch.setattr(output, "get_size", lambda: Size(rows=7, columns=40))
    phases = []
    with create_pipe_input() as source:

        def rendered(ui):
            if ui.is_done or app._chat_shell._busy:
                return
            height = ui.layout.current_window.render_info.window_height
            if not phases:
                assert app._chat_shell._footer == ""
                assert height == 4
                source.send_text("set\r")
                phases.append("set")
            elif len(sessions) == 1 and phases[-1] == "set":
                assert app._chat_shell._footer == "first " * 30
                assert height == 3
                footer = ui.layout.visible_windows[-1]
                assert footer.render_info.window_height == 1
                assert footer.wrap_lines() is False
                source.send_text("replace\r")
                phases.append("replace")
            elif len(sessions) == 2 and phases[-1] == "replace":
                assert app._chat_shell._footer == "second"
                source.send_text("fail\r")
                phases.append("fail")
            elif len(sessions) == 3 and phases[-1] == "fail":
                assert app._chat_shell._footer == "second"
                source.send_text("clear\r")
                phases.append("clear")
            elif len(sessions) == 4 and phases[-1] == "clear":
                assert app._chat_shell._footer == ""
                assert height == 4
                source.send_text("/exit\r")
                phases.append("exit")

        monkeypatch.setattr(
            "picle.chat.Application",
            lambda **kw: Application(**kw, after_render=rendered),
        )
        with create_app_session(input=source, output=output):
            app.onecmd("chat")
    assert app._chat_shell._footer == ""
    assert "first " not in app.stdout.getvalue()
    assert "second" not in app.stdout.getvalue()
    assert "operation failed" in app.stdout.getvalue()
    sessions[0].set_footer("late")
    assert sessions[0]._events.empty()
