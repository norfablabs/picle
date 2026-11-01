"""Tests for the prompt_toolkit interactive-input integration."""

from io import StringIO

import pytest
from prompt_toolkit import PromptSession
from prompt_toolkit.application import create_app_session
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


@pytest.mark.parametrize(
    "keys,expected",
    [
        ("first\x1b\rsecond\r", "first\nsecond"),
        ("first\x1b\rsecond\x1b[A\x1b[Hedited \r", "edited first\nsecond"),
        ("\x1b[200~  first\n/show status\n\x1b[201~\r", "  first\n/show status\n"),
        ("literal?\r", "literal?"),
        ("\r\rhello\r", "hello"),
        ("  \rhello\r", "  hello"),
        ("\x1b[200~" + "line\n" * 20 + "end\x1b[201~\r", "line\n" * 20 + "end"),
    ],
)
def test_chat_editor_edits_and_submits_one_buffer(keys, expected):
    class Root(BaseModel):
        pass

    shell = App(Root, stdout=StringIO())
    shell.use_rich = False
    shell._history = _PicleHistory(None, 100)
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text(keys + "normal\r")
            assert shell._read_interactive_input("You> ", chat=True) == expected
            assert shell._read_interactive_input("") == "normal"
    assert expected in shell._chat_history.get_strings()
    assert expected not in shell._history.get_strings()
    assert expected in shell.stdout.getvalue()


@pytest.mark.parametrize("key,error", [("\x03", KeyboardInterrupt), ("\x04", EOFError)])
def test_chat_editor_interrupts(key, error):
    class Root(BaseModel):
        pass

    shell = App(Root)
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text(key)
            with pytest.raises(error):
                shell._read_interactive_input("", chat=True)


def test_multiline_history_is_kept_only_in_memory(tmp_path):
    path = tmp_path / "history.txt"
    history = _PicleHistory(str(path), length=2)
    for entry in ["first", "second", "multi\nline", "carriage\rreturn"]:
        history.append_string(entry)
    history.save()
    assert history.get_strings() == [
        "first",
        "second",
        "multi\nline",
        "carriage\rreturn",
    ]
    assert _PicleHistory(str(path), length=2).get_strings() == ["first", "second"]


def test_chat_history_is_separate_from_persisted_shell_history(tmp_path):
    class Root(BaseModel):
        class PicleConfig:
            history_file = str(tmp_path / "history.txt")

    shell = App(Root, stdout=StringIO())
    shell._history.append_string("show status")
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text("hello chat\r")
            assert shell._read_interactive_input("", chat=True) == "hello chat"
    shell.postloop()
    assert shell._chat_history.get_strings() == ["hello chat"]
    assert shell._history.get_strings() == ["show status"]
    assert (tmp_path / "history.txt").read_text() == "show status\n"


def test_chat_editor_completion_and_multiline_history(monkeypatch):
    from prompt_toolkit.application import Application

    class Root(BaseModel):
        status: str = None
        status_other: str = None

    shell = App(Root, stdout=StringIO())
    shell.is_chat = True
    with create_pipe_input() as pipe_input:
        sent = []

        def rendered(app):
            if not sent:
                pipe_input.send_text("/sta\t")
                sent.append("tab")
            elif sent == ["tab"] and app.current_buffer.complete_state:
                pipe_input.send_text("\t\rvalue\r")
                sent.append("submit")
            elif sent[-1] == "recall":
                app.loop.call_soon(pipe_input.send_text, "\x1b[A\r")
                sent.append("recalled")

        monkeypatch.setattr(
            "picle.picle.Application",
            lambda **kwargs: Application(**kwargs, after_render=rendered),
        )
        with create_app_session(input=pipe_input, output=DummyOutput()):
            # Tab selects a completion; Enter accepts it, then text remains editable.
            assert shell._read_interactive_input("", chat=True) == "/status value"
            pipe_input.send_text("first\x1b\rsecond\r")
            assert shell._read_interactive_input("", chat=True) == "first\nsecond"
            sent.append("recall")
            assert shell._read_interactive_input("", chat=True) == "first\nsecond"


@pytest.mark.parametrize(
    "setting,keys",
    [
        ("alt+enter", "first\x1b\rsecond\r"),
        ("c-j", "first\nsecond\r"),
        (("c-j",), "first\nsecond\r"),
    ],
)
def test_chat_newline_keys_from_root_config(setting, keys):
    class Root(BaseModel):
        class PicleConfig:
            chat_newline_keys = setting

    shell = App(Root, stdout=StringIO())
    assert shell.chat_newline_keys == setting
    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input, output=DummyOutput()):
            pipe_input.send_text(keys)
            assert shell._read_interactive_input("", chat=True) == "first\nsecond"


@pytest.mark.parametrize("input_height", [5, 8])
def test_chat_editor_viewport_scrolls_and_shrinks(monkeypatch, input_height):
    from prompt_toolkit.application import Application
    from prompt_toolkit.data_structures import Size

    class Root(BaseModel):
        pass

    shell = App(Root, stdout=StringIO())
    output = DummyOutput()
    monkeypatch.setattr(output, "get_size", lambda: Size(rows=24, columns=60))
    viewports = []

    with create_pipe_input() as pipe_input:

        def rendered(app):
            window = app.layout.current_window
            if app.is_done:
                return
            viewports.append((window.render_info.window_height, window.vertical_scroll))
            assert len(app.layout.container.content.children) == 3
            if len(viewports) == 1:
                pipe_input.send_text("\x1b[200~" + "line\n" * 20 + "end\x1b[201~")
            elif len(viewports) == 2:
                monkeypatch.setattr(
                    output, "get_size", lambda: Size(rows=7, columns=40)
                )
                app.renderer.reset()
                app.invalidate()
            else:
                pipe_input.send_text("\r")

        def application(**kwargs):
            return Application(**kwargs, after_render=rendered)

        monkeypatch.setattr("picle.picle.Application", application)
        with create_app_session(input=pipe_input, output=output):
            assert (
                shell._read_interactive_input(
                    "", chat=True, chat_input_height=input_height
                )
                == "line\n" * 20 + "end"
            )
    assert viewports[0] == (input_height, 0)
    assert viewports[1][0] == input_height and viewports[1][1] > 0
    assert viewports[-1][0] == 4 and viewports[-1][1] > 0
