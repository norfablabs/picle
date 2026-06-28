[![Downloads][pepy-downloads-badge]][pepy-downloads-link]
[![PyPI][pypi-latest-release-badge]][pypi-latest-release-link]
[![PyPI versions][pypi-pyversion-badge]][pypi-pyversion-link]
[![Code style: black][black-badge]][black-link]
[![Tests](https://github.com/dmulyalin/picle/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/dmulyalin/picle/actions/workflows/main.yml)

# ![logo](docs/images/logo_small.jpg) PICLE - Python Interactive Command Line Shells

PICLE helps you build interactive CLI shells from Pydantic v2 models.
Think of it as: **your model tree becomes the command tree**.

Built on top of Python's standard library [CMD module](https://docs.python.org/3/library/cmd.html),
[prompt_toolkit](https://python-prompt-toolkit.readthedocs.io/) for interactive input, and
[Pydantic](https://docs.pydantic.dev/) models to construct shell environments.

What you get out of the box:

- command discovery + inline help (`?` / `??`)
- tab completion (works well with nested commands)
- editable, persistent command history
- input validation via Pydantic
- optional pipes (`|`) to post-process output

Docs: https://dmulyalin.github.io/picle/

## Install

```bash
pip install picle
```

Optional extras (Rich output, tables, YAML config support):

```bash
pip install "picle[full]"
```

## A tiny shell app

This creates a small interactive shell:

```
Root
  └─ show
     ├─ version
     └─ clock
```

```python
import time
from typing import Any

from pydantic import BaseModel, Field
from picle import App


class Show(BaseModel):
    version: Any = Field(
        None,
        description="Show software version",
        json_schema_extra={"function": "show_version"},
    )
    clock: Any = Field(
        None,
        description="Show current clock",
        json_schema_extra={"function": "show_clock"},
    )

    @staticmethod
    def show_version():
        return "0.1.0"

    @staticmethod
    def show_clock():
        return time.ctime()


class Root(BaseModel):
    show: Show = Field(None, description="Show commands")

    class PicleConfig:
        prompt = "picle#"
        intro = "PICLE sample app"


if __name__ == "__main__":
    App(Root).start()
```

Try it:

```
picle#show version
0.1.0

picle#show clock
Fri May  2 22:44:01 2025

picle#?
... shows available commands
```

# Comparison With Other Projects

PICLE is not trying to replace every CLI library. It’s mostly for the “network device / DB console / ops shell” style workflow:
you stay in a shell, you explore commands, you get completion + help, and your input is validated.

Some nearby tools and where PICLE fits:

## One-shot CLI command frameworks

Great when you want `mytool subcommand --flags` and exit.

- [argparse](https://docs.python.org/3/library/argparse.html): batteries-included, stable, not interactive by default.
- [click](https://github.com/pallets/click) / [typer](https://github.com/fastapi/typer): excellent UX for subcommands/options, but still “run once and exit”.
- [python-fire](https://github.com/google/python-fire): fast to expose a Python object as CLI, but it’s not focused on interactive shells, completion, or validation the way a model-driven shell is.

You *can* build REPL-like flows with these, but PICLE starts from the REPL/shell side.

## Interactive shell / REPL frameworks

- Python’s built-in [cmd](https://docs.python.org/3/library/cmd.html): the base that PICLE builds on.
- [cmd2](https://github.com/python-cmd2/cmd2): adds a lot of features on top of `cmd` (nice project). PICLE’s angle is different: it uses **Pydantic models as the command tree**, so completion/help/validation all come from the schema.
- [python-nubia](https://github.com/facebookarchive/python-nubia) (archived): similar “interactive shell” spirit, but the project is not maintained and doesn’t integrate with Pydantic.

## TUI / input toolkits

- [prompt-toolkit](https://github.com/prompt-toolkit/python-prompt-toolkit): PICLE uses it for portable line editing, history, and terminal input. PICLE adds the model-driven command tree, parsing, help, completion rules, validation, and dispatch.
- [textual](https://github.com/Textualize/textual): awesome for full-screen TUIs (apps, dashboards). Different goal than a command shell.

## Output formatting helpers

PICLE can use these (optionally) but doesn’t depend on them:

- [rich](https://github.com/Textualize/rich): pretty output rendering
- [tabulate](https://github.com/astanin/python-tabulate): text tables
- [PyYAML](https://github.com/yaml/pyyaml): YAML config support (used by `ConfigModel`)


[black-badge]:                 https://img.shields.io/badge/code%20style-black-000000.svg
[black-link]:                  https://github.com/psf/black
[pypi-pyversion-link]:         https://pypi.python.org/pypi/picle/
[pypi-pyversion-badge]:        https://img.shields.io/pypi/pyversions/picle.svg
[pepy-downloads-link]:         https://pepy.tech/project/picle
[pepy-downloads-badge]:        https://pepy.tech/badge/picle
[pypi-latest-release-badge]:   https://img.shields.io/pypi/v/picle.svg
[pypi-latest-release-link]:    https://pypi.python.org/pypi/picle
