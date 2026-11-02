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


def test_source_cache_sharing_expiry_and_clearing(shell, monkeypatch):
    app, tasks = shell
    calls = []
    now = [100.0]
    monkeypatch.setattr("picle.picle.time.monotonic", lambda: now[0])
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": 10}

    def source(service="all", hosts=None):
        calls.append((service, hosts))
        return ["task-one", "other"]

    tasks.source_name = staticmethod(source)
    line = "tasks service nornir hosts a b name "
    discover(app, "completion", line)
    discover(app, "?", line.replace("service", "svc"))
    assert calls == [("nornir", ["a", "b"])]
    # Local prefix filtering must not alter choices subsequently shown by help.
    assert discover(app, "completion", line + "task") == ["task-one "]
    assert "other" in discover(app, "help", line)
    now[0] = 110.0
    discover(app, "help", line)
    assert len(calls) == 2
    app.clear_source_cache()
    discover(app, "completion", line)
    assert len(calls) == 3
    discover(app, "completion", line.replace("nornir", "other"))
    assert len(calls) == 4
    second = App(app.root, stdout=io.StringIO())
    second.use_rich = False
    discover(second, "completion", line)
    assert len(calls) == 5


def test_source_cache_removes_expired_entries(shell, monkeypatch):
    app, tasks = shell
    now = [100.0]
    monkeypatch.setattr("picle.picle.time.monotonic", lambda: now[0])
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": 10}
    tasks.source_name = staticmethod(lambda service="all": [service])

    discover(app, "completion", "tasks service old name ")
    now[0] = 105.0
    discover(app, "help", "tasks service live name ")
    assert len(app.source_cache) == 2

    now[0] = 110.0
    discover(app, "completion", "tasks service new name ")
    assert sorted(entry[1] for entry in app.source_cache.values()) == [
        ["live"],
        ["new"],
    ]


@pytest.mark.parametrize("ttl", [None, 0, -1])
def test_source_cache_disabled(shell, ttl):
    app, tasks = shell
    calls = []
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": ttl}

    def source():
        calls.append(True)
        return []

    tasks.source_name = staticmethod(source)
    for mode in ["completion", "help"]:
        discover(app, mode, "tasks name ")
    assert len(calls) == 2


def test_source_cache_choice_and_empty_results(shell):
    app, tasks = shell
    calls = []
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": 60}

    def source(choice):
        calls.append(choice)
        return []

    tasks.source_name = staticmethod(source)
    for token in ["", "task", "task", ""]:
        discover(app, "completion", "tasks name " + token)
    discover(app, "help", "tasks name ")
    assert calls == ["", "task"]


def test_source_cache_does_not_cache_errors(shell):
    app, tasks = shell
    calls = []
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": 60}

    def source():
        calls.append(True)
        raise TypeError("source failure")

    tasks.source_name = staticmethod(source)
    for _ in range(2):
        with pytest.raises(TypeError, match="source failure"):
            discover(app, "help", "tasks name ")
    assert len(calls) == 2


def test_source_cache_separates_model_and_field(shell):
    app, tasks = shell
    calls = []

    def source():
        calls.append(True)
        return ["task-one"]

    for model, name in [(tasks, "name"), (tasks, "service"), (app.root, "service")]:
        model.model_fields[name].json_schema_extra = {"source_cache_ttl": 60}
        setattr(model, "source_" + name, staticmethod(source))
    for _ in range(2):
        for line in ["tasks name ", "tasks service ", "service "]:
            discover(app, "help", line)
    assert len(calls) == 3


def test_source_cache_argument_types_and_unsupported_values(shell):
    app, tasks = shell
    calls = []
    tasks.model_fields["name"].json_schema_extra = {"source_cache_ttl": 60}

    def source(flag=None):
        calls.append(flag)
        return []

    tasks.source_name = staticmethod(source)
    for value in [False, 0, {"a": [1, 2], "b": None}, {"b": None, "a": [1, 2]}]:
        tasks.model_fields["flag"].json_schema_extra["presence"] = value
        discover(app, "help", "tasks flag name ")
    assert len(calls) == 3  # False and zero differ; dictionary order does not.
    tasks.model_fields["flag"].json_schema_extra["presence"] = object()
    for _ in range(2):
        with pytest.raises(TypeError, match="JSON serializable"):
            discover(app, "help", "tasks flag name ")
    assert len(calls) == 3


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
