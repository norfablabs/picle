"""Multiline chat editor and execution loop used by PICLE's App."""

import asyncio
from functools import partial
from concurrent.futures import Future
from time import monotonic
from typing import Any, Optional

from prompt_toolkit import Application
from prompt_toolkit.application import get_app, run_in_terminal
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import (
    AnyFormattedText,
    to_formatted_text,
)
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import (
    ConditionalContainer,
    Float,
    FloatContainer,
    HSplit,
    Layout,
    Window,
)
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.widgets import TextArea

from .models import HAS_RICH


class ChatSession:
    """Progress and sequential approvals for the active handler thread."""

    def __init__(self):
        self._events = asyncio.Queue()
        self._closed = False
        self._loop = None
        self._approval = None

    def write(self, text: Any) -> None:
        """Append plain text or an object supported by App.write()."""
        if not self._closed:
            self._loop.call_soon_threadsafe(self._events.put_nowait, ("write", text))

    def set_status(
        self, text: str = "", spinner: bool = False, elapsed: bool = False
    ) -> None:
        """Replace the temporary status line; empty text clears it."""
        if not self._closed:
            self._loop.call_soon_threadsafe(
                self._events.put_nowait,
                (
                    "status",
                    text,
                    bool(text) and spinner,
                    monotonic() if text and elapsed else None,
                ),
            )

    def approve(self, prompt: str) -> bool:
        """Wait in the handler thread for Allow/Deny. Closure means Deny."""
        if self._closed:
            return False
        self._approval = Future()
        self._loop.call_soon_threadsafe(
            self._events.put_nowait, ("approve", prompt, self._approval)
        )
        return self._approval.result()

    def set_footer(self, text: AnyFormattedText = "") -> None:
        """Set plain or prompt-toolkit formatted footer content."""
        if not self._closed:
            self._loop.call_soon_threadsafe(self._events.put_nowait, ("footer", text))


class ChatShell:
    """Own chat rendering and execution while App retains shell integration."""

    def __init__(self, app):
        self.app = app
        self.session = None
        self._footer = ""
        self._busy = False
        self._status = ""
        self._spinner = False
        self._status_started = None
        self._approval = None

    def run(
        self, run_function: callable, kw: dict, picle_config: Any
    ) -> Optional[bool]:
        """Run one persistent chat application using App's shell interfaces."""
        from .picle import callable_expects_argument

        app = self.app
        session = self.session = ChatSession()
        kw = dict(kw)
        if callable_expects_argument(run_function, "chat"):
            kw["chat"] = session
        prompt = getattr(picle_config, "chat_prompt", "> ")
        chat_input_height = getattr(picle_config, "chat_input_height", 5)
        app.is_chat = True
        self._footer = ""
        self._busy = False
        self._status = ""
        self._status_started = None
        self._approval = None
        editor = TextArea(
            multiline=True,
            height=lambda: max(
                1,
                min(
                    chat_input_height,
                    get_app().output.get_size().rows
                    - 3
                    - bool(self._status)
                    - bool(self._approval)
                    - bool(self._footer),
                ),
            ),
            scrollbar=True,
            history=app._chat_history,
            completer=app._prompt_completer if app.completekey else None,
            complete_while_typing=False,
        )
        bindings = KeyBindings()
        newline_keys = app.chat_newline_keys
        if newline_keys == "alt+enter":
            newline_keys = ("escape", "enter")
        elif isinstance(newline_keys, str):
            newline_keys = (newline_keys,)

        @bindings.add("enter")
        def submit(event):
            buffer = event.current_buffer
            if self._busy or self._approval or not buffer.text.strip():
                return
            if buffer.complete_state:
                buffer.complete_state = None
            else:
                buffer.append_to_history()
                line = buffer.text
                buffer.reset()
                self._busy = True
                event.app.create_background_task(execute(line))

        @bindings.add(*newline_keys)
        def newline(event):
            event.current_buffer.insert_text("\n")

        @bindings.add("c-c")
        def interrupt(event):
            if not self._busy:
                event.app.exit(result=True)

        @bindings.add("c-d")
        def eof(event):
            if self._busy:
                return
            if event.current_buffer.text:
                event.current_buffer.delete()
            else:
                event.app.exit(result=None)

        @bindings.add("y", filter=Condition(lambda: self._approval is not None))
        @bindings.add("Y", filter=Condition(lambda: self._approval is not None))
        def allow(event):
            self._approval[1].set_result(True)
            self._approval = None
            event.app.layout.focus(editor)

        @bindings.add("n", filter=Condition(lambda: self._approval is not None))
        @bindings.add("N", filter=Condition(lambda: self._approval is not None))
        def deny(event):
            self._approval[1].set_result(False)
            self._approval = None
            event.app.layout.focus(editor)

        async def drain_output():
            while True:
                event = await session._events.get()
                try:
                    if event[0] == "write":
                        text = event[1]
                        if isinstance(text, str):
                            await run_in_terminal(
                                lambda: (
                                    app.stdout.write(
                                        text
                                        + ("" if text.endswith("\n") else app.newline)
                                    ),
                                    app.stdout.flush(),
                                )
                            )
                        else:
                            await run_in_terminal(partial(app.write, text))
                    elif event[0] == "status":
                        self._status, self._spinner, self._status_started = event[1:]
                    elif event[0] == "footer":
                        to_formatted_text(event[1])
                        self._footer = event[1]
                    else:
                        self._approval = event[1:]
                        ui.layout.focus(approval_control)
                    ui.invalidate()
                except Exception as error:
                    await run_in_terminal(partial(app.write_error, str(error)))
                finally:
                    session._events.task_done()

        async def execute(line):
            try:
                await run_in_terminal(
                    lambda: (
                        app.stdout.write(f"{prompt}{line}{app.newline}"),
                        app.stdout.flush(),
                    )
                )
                if (
                    "\n" not in line
                    and "\r" not in line
                    and line.strip().startswith("/")
                ):
                    command = line.strip()[1:]
                    if command == "exit":
                        if getattr(picle_config, "chat_commands_model", None):
                            app.do_exit(command)
                        ui.exit(result=None)
                        return
                    stop = await run_in_terminal(
                        lambda: app.onecmd(command), in_executor=True
                    )
                    if stop is True:
                        ui.exit(result=True)
                    return
                failure = None
                try:
                    ret = await asyncio.to_thread(run_function, line, **kw)
                    if hasattr(ret, "__next__"):
                        raise TypeError(
                            "Chat handlers must return a complete response; streaming is not supported"
                        )
                except Exception as error:
                    failure = error
                await session._events.join()
                self._status = ""
                self._status_started = None
                self._spinner = False
                if failure is not None:
                    await run_in_terminal(lambda: app.write_error(str(failure)))
                    return
                if ret is None or ret is True:
                    ui.exit(result=ret)
                    return

                def render_response():
                    result = ret
                    if not result:
                        return
                    outputter = None
                    outputter_kwargs = {}
                    if isinstance(result, tuple) and len(result) == 2:
                        result, outputter = result
                    elif isinstance(result, tuple) and len(result) == 3:
                        result, outputter, outputter_kwargs = result
                    elif hasattr(picle_config, "outputter"):
                        outputter = picle_config.outputter
                        outputter_kwargs = getattr(picle_config, "outputter_kwargs", {})
                    if callable(outputter):
                        app.write(outputter(result, **outputter_kwargs))
                    elif outputter is True:
                        app.write(result)
                    elif result:
                        prefix = getattr(picle_config, "chat_response_prefix", "")
                        style = getattr(picle_config, "chat_response_style", None)
                        result = f"{prefix}{result}"
                        if style and app.use_rich and HAS_RICH:
                            result = f"[{style}]{result}[/{style}]"
                        app.write(result)

                await run_in_terminal(render_response, in_executor=True)
            except Exception as error:
                await run_in_terminal(lambda: app.write_error(str(error)))
            finally:
                if session._approval is not None and not session._approval.done():
                    session._approval.set_result(False)
                self._approval = None
                self._status = ""
                self._status_started = None
                self._spinner = False
                self._busy = False
                if not ui.is_done:
                    ui.layout.focus(editor)
                    ui.invalidate()

        def start():
            session._loop = asyncio.get_running_loop()
            ui.create_background_task(drain_output())

        approval_control = FormattedTextControl(
            lambda: (
                f"{self._approval[0]}  [Y] Allow / [N] Deny" if self._approval else ""
            ),
            focusable=True,
        )

        ui = Application(
            layout=Layout(
                FloatContainer(
                    content=HSplit(
                        [
                            ConditionalContainer(
                                Window(
                                    height=1,
                                    content=FormattedTextControl(
                                        lambda: self._status
                                        + (
                                            (".", "..", "...")[
                                                int(monotonic() * 2) % 3
                                            ].ljust(3)
                                            if self._spinner
                                            else ""
                                        )
                                        + (
                                            "  {:02d}:{:02d}".format(
                                                *divmod(
                                                    int(
                                                        monotonic()
                                                        - self._status_started
                                                    ),
                                                    60,
                                                )
                                            )
                                            if self._status_started is not None
                                            else ""
                                        )
                                    ),
                                ),
                                filter=Condition(lambda: bool(self._status)),
                            ),
                            ConditionalContainer(
                                Window(height=1, content=approval_control),
                                filter=Condition(lambda: self._approval is not None),
                            ),
                            Window(height=1, char="─"),
                            editor,
                            Window(height=1, char="─"),
                            ConditionalContainer(
                                Window(
                                    height=1,
                                    wrap_lines=False,
                                    content=FormattedTextControl(lambda: self._footer),
                                ),
                                filter=Condition(lambda: bool(self._footer)),
                            ),
                        ]
                    ),
                    floats=[
                        Float(xcursor=True, ycursor=True, content=CompletionsMenu())
                    ],
                ),
                focused_element=editor,
            ),
            key_bindings=bindings,
            full_screen=False,
            erase_when_done=True,
            refresh_interval=0.1,
        )
        try:
            return ui.run(pre_run=start)
        finally:
            session._closed = True
            self._footer = ""
            if session._approval is not None and not session._approval.done():
                session._approval.set_result(False)
            self._status = ""
            self._status_started = None
            self._approval = None
            self._busy = False
            app.is_chat = False
