"""Drive the persistent chat UI for existing scripted command tests."""

import inspect

import pytest
from prompt_toolkit.application import Application, create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys

from picle.chat import ChatShell


@pytest.fixture
def scripted_chat(monkeypatch):
    original = ChatShell.run

    def run(shell, run_function, kw, config):
        reader = shell.app._read_interactive_input
        if inspect.ismethod(reader):
            return original(shell, run_function, kw, config)

        def rendered(ui):
            if ui.is_done or shell._busy:
                return
            try:
                line = reader(
                    getattr(config, "chat_prompt", "> "),
                    inline_help=False,
                    chat=True,
                    chat_input_height=getattr(config, "chat_input_height", 5),
                )
                if line.strip():
                    ui.current_buffer.text = line
                    ui.key_processor.feed(KeyPress(Keys.ControlM, "\r"))
                    ui.key_processor.process_keys()
                else:
                    ui.invalidate()
            except EOFError:
                ui.exit(result=None)
            except KeyboardInterrupt:
                ui.exit(result=True)
            except Exception as error:
                ui.exit(exception=error)

        with monkeypatch.context() as patch:
            patch.setattr(
                "picle.chat.Application",
                lambda **kwargs: Application(**kwargs, after_render=rendered),
            )
            with create_pipe_input() as source:
                with create_app_session(input=source, output=DummyOutput()):
                    return original(shell, run_function, kw, config)

    monkeypatch.setattr(ChatShell, "run", run)
