"""Tests for the prompt_toolkit interactive-input integration."""

from io import StringIO

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.completion import CompleteEvent
from prompt_toolkit.document import Document
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pydantic import BaseModel

from picle.picle import App, _PicleCompleter, _PicleHistory
from picle.picle_cmd import Cmd


def test_cmdloop_preserves_cmdqueue_and_noninteractive_input():
    events = []

    class TestCmd(Cmd):
        intro = None
        use_rawinput = False

        def precmd(self, line):
            events.append(("precmd", line))
            return line

        def onecmd(self, line):
            events.append(("onecmd", line))
            return line == "stop"

        def postcmd(self, stop, line):
            events.append(("postcmd", line))
            return stop

        def postloop(self):
            events.append(("postloop", None))

    shell = TestCmd(stdin=StringIO("stop\r\n"), stdout=StringIO())
    shell.cmdqueue.append("queued")
    shell.cmdloop()

    assert events == [
        ("precmd", "queued"),
        ("onecmd", "queued"),
        ("postcmd", "queued"),
        ("precmd", "stop"),
        ("onecmd", "stop"),
        ("postcmd", "stop"),
        ("postloop", None),
    ]


def test_prompt_toolkit_completer_adapts_document_context():
    class CompletionApp:
        context = None

        def get_completion_matches(self, text, line, begidx, endidx):
            self.context = (text, line, begidx, endidx)
            return ["status "]

    app = CompletionApp()
    completer = _PicleCompleter(app)
    document = Document("  show sta", cursor_position=len("  show sta"))

    matches = list(
        completer.get_completions(document, CompleteEvent(completion_requested=True))
    )

    assert app.context == ("sta", "show sta", 5, 8)
    assert len(matches) == 1
    assert matches[0].text == "status "
    assert matches[0].start_position == -3


def test_history_loads_readline_file_and_honors_save_length(tmp_path):
    history_path = tmp_path / "history.txt"
    history_path.write_text("one\ntwo\n", encoding="utf-8")
    history = _PicleHistory(str(history_path), length=2)

    assert history.get_strings() == ["one", "two"]

    history.append_string("three")
    history.save()

    assert history_path.read_text(encoding="utf-8") == "two\nthree\n"


def test_app_reuses_one_prompt_session(monkeypatch):
    sessions = []

    class FakePromptSession:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.prompts = []
            sessions.append(self)

        def prompt(self, prompt):
            self.prompts.append(prompt)
            return "accepted"

    class Root(BaseModel):
        pass

    monkeypatch.setattr("picle.picle.PromptSession", FakePromptSession)
    shell = App(Root)

    assert shell._read_interactive_input("first> ") == "accepted"
    assert shell._read_interactive_input("second> ") == "accepted"
    assert len(sessions) == 1
    assert sessions[0].prompts == ["first> ", "second> "]
    assert sessions[0].kwargs["history"] is shell._history
    assert sessions[0].kwargs["completer"] is shell._prompt_completer
    assert sessions[0].kwargs["key_bindings"] is shell._prompt_key_bindings


def test_question_mark_requests_help_without_changing_buffer(monkeypatch):
    class Root(BaseModel):
        pass

    shell = App(Root)
    document = Document("show ", cursor_position=len("show "))
    callbacks = []
    help_lines = []
    monkeypatch.setattr(
        "picle.picle.run_in_terminal",
        lambda callback, **kwargs: callbacks.append((callback, kwargs)),
    )
    monkeypatch.setattr(shell, "process_help_command", help_lines.append)

    shell._request_inline_help(document)
    callback, options = callbacks.pop()
    callback()
    assert options == {"render_cli_done": True}

    shell._request_inline_help(document)
    callback, options = callbacks.pop()
    callback()
    assert options == {"render_cli_done": True}

    assert help_lines == ["show ?", "show ??"]
    assert document.text == "show "


def test_question_mark_key_binding_runs_during_prompt(monkeypatch):
    class Root(BaseModel):
        pass

    shell = App(Root)
    help_lines = []
    monkeypatch.setattr(shell, "process_help_command", help_lines.append)

    with create_pipe_input() as pipe_input:
        shell._prompt_session = PromptSession(
            history=shell._history,
            completer=shell._prompt_completer,
            complete_while_typing=False,
            key_bindings=shell._prompt_key_bindings,
            input=pipe_input,
            output=DummyOutput(),
        )
        pipe_input.send_text("show ?\r")

        assert shell._read_interactive_input("") == "show "

    assert help_lines == ["show ?"]


def test_inline_help_is_disabled_for_nested_input():
    class Root(BaseModel):
        pass

    shell = App(Root)
    with create_pipe_input() as pipe_input:
        shell._prompt_session = PromptSession(
            history=shell._history,
            completer=shell._prompt_completer,
            complete_while_typing=False,
            key_bindings=shell._prompt_key_bindings,
            input=pipe_input,
            output=DummyOutput(),
        )
        pipe_input.send_text("value?\r")

        assert shell._read_interactive_input("", inline_help=False) == "value?"

    assert shell._inline_help_enabled is False


def test_prompt_session_maps_ctrl_d_to_eof():
    class Root(BaseModel):
        pass

    shell = App(Root)
    with create_pipe_input() as pipe_input:
        shell._prompt_session = PromptSession(
            history=shell._history,
            completer=shell._prompt_completer,
            complete_while_typing=False,
            input=pipe_input,
            output=DummyOutput(),
        )
        pipe_input.send_text("line 1\r\x04")

        assert shell._read_interactive_input("") == "line 1"
        with pytest.raises(EOFError):
            shell._read_interactive_input("")
