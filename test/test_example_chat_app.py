import sys
import unittest.mock
import pytest

from picle import App

from .example_chat_app import MockChatState, Root

pytestmark = pytest.mark.usefixtures("scripted_chat")


def _collect_output(mock_stdout) -> str:
    return "".join(str(call.args[0]) for call in mock_stdout.write.call_args_list)


def _new_shell():
    mock_stdin = unittest.mock.create_autospec(sys.stdin)
    mock_stdout = unittest.mock.create_autospec(sys.stdout)
    shell = App(Root, stdin=mock_stdin, stdout=mock_stdout)
    shell.use_rich = False
    shell.onecmd("top")
    mock_stdout.write.reset_mock()
    return shell, mock_stdout


def test_chat_echo_uses_session_and_user():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell, "_read_interactive_input", side_effect=["hello world", EOFError]
    ):
        shell.onecmd("chat session_id sess-001 user alice")

    output = _collect_output(mock_stdout)
    assert "AI> [model=mock-1] [turn=1] [session=sess-001] alice: dlrow olleh" in output
    assert MockChatState.turn == 1
    assert MockChatState.history == ["hello world"]


def test_chat_rich_objects_render_in_sample_app(monkeypatch):
    rich_console = pytest.importorskip("rich.console")
    from io import StringIO

    shell, _ = _new_shell()
    shell.use_rich = True
    rendered = StringIO()
    monkeypatch.setattr(
        "picle.picle.RICHCONSOLE",
        rich_console.Console(
            file=rendered,
            force_terminal=True,
            color_system="truecolor",
            no_color=False,
            legacy_windows=False,
            width=80,
        ),
    )
    with unittest.mock.patch.object(
        shell, "_read_interactive_input", side_effect=["rich", "/exit"]
    ):
        shell.onecmd("chat session_id demo user alice")
    output = rendered.getvalue()
    assert "Rich progress message" in output
    assert "\x1b[1;32m" in output
    assert "Step" in output and "Status" in output
    assert "Example" in output and "Complete" in output
    assert output.count("Rich output complete") == 1


def test_chat_slash_show_commands_are_dispatched():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell,
        "_read_interactive_input",
        side_effect=["/show usage", "/show status", EOFError],
    ):
        shell.onecmd("chat session_id sess-002 user bob")

    output = _collect_output(mock_stdout)
    assert "Current usage  1234 tokens." in output
    assert "model=mock-1; turns=0; messages=0" in output


def test_chat_set_model_changes_following_response():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell,
        "_read_interactive_input",
        side_effect=["/set_model mock-2", "hello", EOFError],
    ):
        shell.onecmd("chat session_id sess-003 user eve")

    output = _collect_output(mock_stdout)
    assert "mock model switched to 'mock-2'" in output
    assert "AI> [model=mock-2] [turn=1] [session=sess-003] eve: olleh" in output


def test_chat_reset_clears_state_and_restarts_turn_counter():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell,
        "_read_interactive_input",
        side_effect=["first", "/reset", "/show status", "second", EOFError],
    ):
        shell.onecmd("chat session_id sess-004 user alice")

    output = _collect_output(mock_stdout)
    assert "AI> [model=mock-1] [turn=1] [session=sess-004] alice: tsrif" in output
    assert "mock chat state reset" in output
    assert "model=mock-1; turns=0; messages=0" in output
    assert "AI> [model=mock-1] [turn=1] [session=sess-004] alice: dnoces" in output
    assert MockChatState.history == ["second"]


def test_chat_complete_response_writes_with_prefix():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell,
        "_read_interactive_input",
        side_effect=["stream token stream", EOFError],
    ):
        shell.onecmd("chat session_id sess-005 user tom")

    output = _collect_output(mock_stdout)
    assert "AI> [model=mock-1] [turn=1] [session=sess-005] tom: TOKEN STREAM" in output


def test_chat_exit_command_leaves_chat_mode():
    MockChatState.reset()
    shell, _ = _new_shell()

    with unittest.mock.patch.object(
        shell, "_read_interactive_input", side_effect=["/exit"]
    ):
        shell.onecmd("chat session_id sess-006 user sam")

    assert shell.is_chat is False
    assert shell.prompt == "example-chat#"
    assert len(shell.shells) == 1


def test_chat_run_can_exit_with_none_return():
    MockChatState.reset()
    shell, mock_stdout = _new_shell()

    with unittest.mock.patch.object(
        shell, "_read_interactive_input", side_effect=["bye"]
    ):
        shell.onecmd("chat session_id sess-007 user sam")

    output = _collect_output(mock_stdout)
    assert "AI> " not in output
    assert shell.is_chat is False
    assert MockChatState.turn == 0
