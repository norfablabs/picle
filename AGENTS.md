# PICLE (repo context for code assistants)

PICLE is a framework for building interactive CLI shells from Pydantic v2 models.
It wraps Python’s standard `cmd.Cmd` loop and treats a command line as a path through a model tree:

- Each token that matches a model field name (or field `alias` / `serialization_alias`) moves the parser deeper.
- Tokens after a leaf field become that field’s value(s).
- A model can execute either:
  - `run(**kwargs)` if it exists, or
  - a field-specific `json_schema_extra["function"]` staticmethod.

This repository is intentionally lightweight; most behavior lives in `picle/picle.py`.

## Where to look

- `picle/picle.py`: `App` (the shell). Parsing, completion, help, piping, execution, output.
- `picle/models.py`: built-in pipe functions (filters + outputters) and built-in `man` commands.
- `picle/utils.py`: helpers (exception wrapper, JSON schema generator).
- `docs/`: MkDocs documentation sources.
- `test/`: pytest tests and sample shell apps.

## Core concepts (how a command line is interpreted)

PICLE reads a line and builds a list of “command segments”. Segments are separated by the pipe token `|`.
Each segment is parsed into a list of model dicts. Roughly:

```
line -> parse_command() -> [segment0_models, segment1_models, ...]

segment_models is a list of nested model references:
  [{model: Root, fields: [...]}, {model: SubModel, fields: [...]}, ...]

fields are collected as:
  {name, field (FieldInfo), values, json_schema_extra}
```

Execution (`App.default`) then processes segments left-to-right:

- Segment 0:
  - build kwargs = `shell_defaults` + per-model defaults + collected arguments
  - validate using Pydantic (`_validate_values`)
  - call `model.run(**kwargs)` if present, else call staticmethod named by field `json_schema_extra["function"]`
- Segment N (after a `|`):
  - call `model.run(previous_result, **kwargs)` (or a field function) to transform the previous segment’s output

After execution, PICLE applies processors/outputters (see below) and writes output.

## Help and completion

- Inline help: end a line with `?` or `??`.
  - `?` prints the current command’s available next tokens.
  - `??` prints the same with more verbose field details.
- `help` command delegates to the same model help builder.
- Completion uses `cmd.Cmd` hooks:
  - `completenames` for the first token
  - `completedefault` for subsequent tokens

Resolution rules:
- exact match by field name, `alias`, or `serialization_alias`
- prefix matches trigger “incomplete command” messaging and completion suggestions

## Model/field metadata that changes behavior

PICLE reads extra behavior hints from `Field(..., json_schema_extra={...})`.
Common keys:

- `function`: name of a `@staticmethod` on the model to call (used when `run()` is absent)
- `presence`: if a field is referenced but no value is provided, set the field value to this constant
- `processors`: list of callables applied to the command result (field-level)
- `outputter`: callable used to render the final result (field-level override)
- `outputter_kwargs`: kwargs passed into `outputter`
- `multiline`: when value is the literal `input`, prompt for multi-line input until EOF
- `root_model`: pass the root model into the called function as `root_model=...`
- `picle_app`: pass the `App` instance into the called function as `picle_app=...`

Model-level configuration is provided via an inner `PicleConfig` class (if present).
`App.__init__` pulls these values with `getattr` guarded by `hasattr`.

## Defaults behavior

PICLE maintains `shell_defaults` (a dict of non-None default values from current shells).
When entering subshells, defaults can be accumulated; when exiting shells, defaults are popped.
Defaults are merged into kwargs for the first segment only.

## Subshells

If `Model.PicleConfig.subshell = True` and the user navigates to that model without providing arguments,
PICLE pushes that model onto the shell stack and updates the prompt.
Global commands for shell navigation:

- `exit`: leave current subshell
- `top`: return to the root shell
- `end`: exit the application
- `pwd`: show shell path
- `cls`: clear screen

## Pipe support

If `Model.PicleConfig.pipe` is set, the token `|` starts a new segment.
Pipe model resolution:

- `pipe = "self"`: re-use current model
- `pipe = "some.module.Model"`: import by string
- `pipe = SomeModel`: use the provided model class

Built-in pipe model: `picle.models.PipeFunctionsModel` (includes filters and outputters).

## Output and outputters

Output is written via `App.write()`:
- if Rich is installed and `use_rich=True`, uses `rich.Console.print`
- otherwise writes to `stdout` with `newline` handling

Output selection order in `default()`:

1) If the function returns a tuple:
   - `(result, outputter)` or `(result, outputter, outputter_kwargs)`
2) Else, if the last field’s `json_schema_extra["outputter"]` is set
3) Else, if `Model.PicleConfig.outputter` is set
4) Else, fall back to `App.write(result)`

Note: “processors” exist at two levels:
- field-level processors run after the segment execution
- model-level `PicleConfig.processors` run for the first segment only

## Built-in `man` commands

`App` mounts `picle.models.MAN` at path `man` during initialization.

- `man tree [path]`: renders a command tree (Rich required)
- `man json-schema [path]`: prints JSON schema for a model (path is dot-separated)

## Dev workflows

This repo uses Poetry (`pyproject.toml`). Typical commands:

- Install (dev): `poetry install`
- Run tests: `poetry run pytest -q`
- Format: `poetry run black .`
- Lint (if configured locally): `poetry run flake8` / `poetry run pylint picle`
- Build docs: `poetry run mkdocs serve`

## Assistant guidelines (what to preserve)

- Pydantic v2 is the target; avoid v1 APIs.
- Keep behavior compatible with `cmd.Cmd` completion/help hooks.
- Optional dependencies (`rich`, `tabulate`, `pyyaml`) must remain optional.
- Documentation style in this repo prefers short, flat pages with minimal section nesting.
