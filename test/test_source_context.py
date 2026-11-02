"""Context forwarding through real completion and help entry points."""

import io

import pytest
from pydantic import BaseModel, Field

from picle import App


@pytest.fixture
def shell():
    class Tasks(BaseModel):
        service: str = Field(None, alias="svc", serialization_alias="service-name")
        enabled: bool = None
        count: int = None
        hosts: list[str] = None
        flag: bool = Field(None, json_schema_extra={"presence": True})
        choice: str = None
        name: str = None

        class PicleConfig:
            pipe = "self"

    class Root(BaseModel):
        service: str = None
        tasks: Tasks = None

    app = App(Root, stdout=io.StringIO())
    app.use_rich = False
    return app, Tasks


def discover(app, mode, line):
    if mode == "completion":
        text = line.rsplit(" ", 1)[-1]
        return app.completedefault(text, line, len(line) - len(text), len(line))
    app.do_help(line + {"help": "", "?": "?", "??": "??"}[mode])
    return app.stdout.getvalue()


@pytest.mark.parametrize("mode", ["completion", "help", "?", "??"])
@pytest.mark.parametrize("service", ["service", "svc", "service-name"])
def test_selected_service_and_source_defaults(shell, mode, service):
    app, tasks = shell
    calls = []

    def source(service="all", workers="any"):
        calls.append((service, workers))
        return ["task-one"]

    tasks.source_name = staticmethod(source)
    assert "task-one" in str(discover(app, mode, f"tasks {service} nornir name "))
    assert calls == [("nornir", "any")]


@pytest.mark.parametrize("mode", ["completion", "help"])
@pytest.mark.parametrize(
    "line,expected",
    [
        ("tasks name ", {"choice": ""}),
        ("service ancestor tasks name ", {"service": "ancestor", "choice": ""}),
        (
            "service ancestor tasks service near name ",
            {"service": "near", "choice": ""},
        ),
        ("tasks service nornir | name ", {"choice": ""}),
        (
            "tasks enabled False count 0 hosts a b flag name ",
            {
                "enabled": False,
                "count": 0,
                "hosts": ["a", "b"],
                "flag": True,
                "choice": "",
            },
        ),
        ('tasks service "" name ', {"service": "", "choice": ""}),
        ("tasks enabled None name ", {"enabled": None, "choice": ""}),
        ("tasks choice command-value name ", {"choice": ""}),
    ],
)
def test_parsed_context_and_scope(shell, mode, line, expected):
    app, tasks = shell
    calls = []

    def source(service=..., enabled=..., count=..., hosts=..., flag=..., choice=""):
        calls.append(
            {
                name: value
                for name, value in locals().items()
                if value is not ... and name != "calls"
            }
        )
        return ["task-one"]

    tasks.source_name = staticmethod(source)
    discover(app, mode, line)
    assert calls == [expected]


@pytest.mark.parametrize("mode", ["completion", "help"])
def test_argument_filtering(shell, mode):
    app, tasks = shell
    calls = []

    def source(service="all", workers="any", choice=""):
        calls.append((service, workers, choice))
        return ["task-one"]

    tasks.source_name = staticmethod(source)
    discover(app, mode, "tasks service nornir count 0 name ")
    assert calls == [("nornir", "any", "")]


@pytest.mark.parametrize("mode", ["completion", "help"])
@pytest.mark.parametrize("kind", ["no_arguments", "choice", "positional"])
def test_compatible_source_signatures(shell, mode, kind):
    app, tasks = shell
    calls = []

    def no_arguments():
        calls.append({})
        return ["task-one"]

    def choice(choice):
        calls.append({"choice": choice})
        return ["task-one"]

    def positional(service="default", /, *hosts, **kwargs):
        calls.append({"service": service, "hosts": hosts, **kwargs})
        return ["task-one"]

    sources = {
        "no_arguments": no_arguments,
        "choice": choice,
        "positional": positional,
    }
    tasks.source_name = staticmethod(sources[kind])
    discover(app, mode, "tasks service nornir hosts a b name ")
    expected = {"choice": ""} if kind == "choice" else {}
    if kind == "positional":
        expected = {"service": "default", "hosts": ()}
    assert calls == [expected]


@pytest.mark.parametrize("mode", ["completion", "help"])
def test_keyword_only_and_kwargs_receive_no_context(shell, mode):
    app, tasks = shell
    calls = []

    def source(*, service="all", **kwargs):
        calls.append((service, kwargs))
        return ["task-one"]

    tasks.source_name = staticmethod(source)
    discover(app, mode, "tasks service nornir count 0 name ")
    assert calls == [("all", {})]


def test_completion_passes_current_choice(shell):
    app, tasks = shell
    calls = []

    def source(choice):
        calls.append(choice)
        return ["task-one", "other"]

    tasks.source_name = staticmethod(source)
    assert discover(app, "completion", "tasks name task") == ["task-one "]
    assert calls == ["task"]


@pytest.mark.parametrize("mode", ["completion", "help"])
@pytest.mark.parametrize("missing", [False, True])
def test_source_errors_follow_existing_handling_without_retry(shell, mode, missing):
    app, tasks = shell
    calls = []

    def source(service="all"):
        calls.append(service)
        raise TypeError("source failed internally")

    def required(service, /):
        calls.append(service)
        return []

    tasks.source_name = staticmethod(required if missing else source)
    if mode == "help":
        with pytest.raises(TypeError):
            discover(app, mode, "tasks name ")
    else:
        assert discover(app, mode, "tasks name ") == []
        assert "TypeError" in app.stdout.getvalue()
    assert calls == ([] if missing else ["all"])
