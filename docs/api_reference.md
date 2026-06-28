# PICLE API reference

This page describes the configuration hooks PICLE reads from your Pydantic models and fields.
It focuses on the parts you use when defining a shell (config, field metadata, execution, and output).
For full API docs of `App` and built-in models, keep reading to the mkdocstrings reference at the bottom.

## `PicleConfig` Model Level Configuration

Any Pydantic model may define an inner `PicleConfig` class. PICLE reads attributes from it (when present).
Only a few are required; most are optional quality-of-life switches.

`PicleConfig` is intentionally “open-ended”: the core `App` reads a known set of attributes (documented below),
and specific built-in models may honor additional `PicleConfig` keys (for example, `ConfigModel`).

| Name | Meaning |
| --- | --- |
| `ruler` | Separator line char used by `cmd` help formatting (empty disables) |
| `intro` | Banner printed on shell start |
| `prompt` | Prompt string |
| `use_rich` | If `True` and Rich is installed, print via Rich console |
| `newline` | Output newline, default `\r\n` |
| `completekey` | Enables interactive Tab completion; set to `None` to disable it, default `tab` |
| `pipe` | Enables `|` and selects the pipe model (`"self"`, import string, or model class) |
| `processors` | List of callables applied to the first command result |
| `outputter` | Callable used to render output when not overridden |
| `outputter_kwargs` | Extra kwargs passed into `outputter` |
| `history_length` | Maximum number of commands written to the persistent history file, default 100; a negative value keeps all entries |
| `history_file` | Filename to persistently store commands history, default `./picle_history.txt` |
| `subshell` | If `True`, navigating to this model with no args enters a subshell (prompt changes, model is pushed onto a stack) |
| `methods_override` | Dict of `{app_method_name: model_method_name}` used to override `App` methods at runtime |

Interactive input uses one persistent `prompt_toolkit.PromptSession` for line editing,
completion, cursor movement, and Up/Down history. Setting `App.use_rawinput = False`
keeps the non-interactive `stdin.readline()` path and does not create a prompt session.

## `json_schema_extra` Field Level Configuration

PICLE reads extra behavior from fields definitions - `Field(..., json_schema_extra={...})`.

Note: command tokens come from the field name (or its `alias` / `serialization_alias`), not from the Pydantic class name.

| Key | Meaning |
| --- | --- |
| `function` | Name of a model `@staticmethod` to call when `run()` is absent |
| `presence` | Constant value used when field is referenced without a value |
| `processors` | List of callables applied to the command result |
| `outputter` | Callable that formats output for this field (overrides model outputter) |
| `outputter_kwargs` | Extra kwargs passed into `outputter` |
| `multiline` | If `True`, the literal value `input` triggers multi-line collection |
| `root_model` | If `True`, pass the app root model as `root_model=...` |
| `picle_app` | If `True`, pass the `App` instance as `picle_app=...` |
| `use_parent_run` | If `True` (default), and the leaf model has no `run()`, PICLE searches parent models for a `run()` to execute. If `False`, the command errors unless the leaf model defines `run()` or `function`. |
| `pkey` | Primary key name to use for dynamic dictionary models |
| `pkey_description` | Description of dynamic dictionary model primary key |

## Handling of `function` Argument vs `run()` Method

Execution is resolved like this:

1. If the last referenced field sets `json_schema_extra={"function": "method_name"}`, PICLE calls `getattr(model, method_name)(**kwargs)`.
2. If the current model has `run`, PICLE calls `model.run(**kwargs)`.
3. if `json_schema_extra={"use_parent_run": True}` set on the field, backtracks parent models and executes first found `run()` method.

This lets small models define many “command -> staticmethod” fields, while larger models can centralize behavior in `run()`.

## Callable Signatures

PICLE builds callable `**kwargs` from collected field values and calls either `run()` or the field-level `function`. It can also inject extra context if callable declares a matching argument name:

- `root_model` - if callable signature includes `root_model` adds `self.root` model to callable arguments e.g. `root_model=self.root`
- `picle_app` - if callable signature includes `picle_app` adds `self` to callable arguments e.g. `picle_app=self`
- `shell_command` - if callable signature includes `shell_command` adds parsed command context for the current segment: a list of model dictionaries produced by `parse_command` method. This is useful when your function needs to inspect the command path, model defaults, or other parsing details.

## PICLE App

::: picle.App

## PICLE Build In Models

::: picle.models.Filters
::: picle.models.Outputters
::: picle.models.PipeFunctionsModel
::: picle.models.MAN
