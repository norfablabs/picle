# Command Discovery

PICLE's discovery flow is model-driven. The same field metadata powers inline help, the `help` command, tab completion, and the built-in `man` commands.

## Example Model

```python
from enum import Enum
from typing import List, Union
from pydantic import BaseModel, Field, StrictStr


class ConnectionPlugin(str, Enum):
    netmiko = "netmiko"
    napalm = "napalm"
    pyats = "pyats"
    scrapli = "scrapli"


class TargetFilters(BaseModel):
    hosts: Union[StrictStr, List[StrictStr]] = Field(
        None, description="Select hostnames to run this task for"
    )

    @staticmethod
    def source_hosts():
        return ["ceos1", "ceos2", "ceos3"]


class DeviceCli(TargetFilters):
    commands: Union[StrictStr, List[StrictStr]] = Field(
        ..., description="CLI commands to send to devices"
    )
    plugin: ConnectionPlugin = Field("netmiko", description="Connection plugin name")

    class PicleConfig:
        subshell = True


class DeviceTools(BaseModel):
    cli: DeviceCli = Field(None, description="Send CLI commands to devices")


class Root(BaseModel):
    devices: DeviceTools = Field(None, description="Device operations")
```

## Inline Help

Press `?` to show the next valid command field immediately. The current command
stays in the input buffer so you can continue editing it after reading the help.

Press `?` twice to show the same list with extra details such as defaults and field
types.

The key is not inserted into the command buffer. This binding applies only to the
main command prompt; `?` remains ordinary text in multi-line and chat input.

```text
picle#devices?
 ... available fields under `devices` ...

picle#devices cli commands?
 <'commands' value>    CLI commands to send to devices

picle#devices cli??
 ... the same fields, plus defaults and field types ...
```

If a field is backed by an enum, help prints the allowed values.

If a model defines `source_<field>()`, help uses that method to show dynamic choices.

```text
picle#help devices cli plugin
 <'plugin' value>    netmiko, napalm, pyats, scrapli

picle#help devices cli hosts
 <'hosts' value>    ceos1, ceos2, ceos3
```

If the current model supports subshell entry, help also shows `<ENTER>`.

```text
picle#help devices cli
 ...
 <ENTER>    Enter command subshell
```

## `help`

`help` uses the same parser as normal command entry, so it understands nested models, aliases, enum values, and partial matches.

```text
picle#help
 ... top-level commands plus built-in commands like exit, top, pwd, end, cls ...

picle#help devices
 ... fields under `devices` ...

picle#help dev
 ... partial-match help for `devices` ...
```

## Tab Completion

Tab completion uses `prompt_toolkit` for terminal input and delegates candidates to
PICLE's existing `cmd`-style `completenames()` and `completedefault()` hooks.

- The first token completes top-level fields and built-in commands such as `exit`, `top`, and `help`.
- Nested completion works after you have already entered part of a command path.
- Enum fields complete from enum values.
- `source_<field>` methods feed completion candidates for dynamic values, `source_<field>` can have `choice` argument defined to receive partial current value for the field, to alter return options behaviour
- Multiline fields complete the special `load-terminal` token.

```text
devices cli <TAB>
  -> suggests fields such as `commands`, `hosts`, and `plugin`

devices cli plugin net<TAB>
  -> completes `netmiko`

devices cli hosts ceos<TAB>
  -> completes values from `source_hosts()`
```

## Partial Matches And Suggestions

PICLE distinguishes between incomplete commands and incorrect commands.

```text
picle#dev
Incomplete command, possible completions: devices
```

If the token does not belong to the current model, PICLE prints an error. When there are close matches, it appends a `Did you mean` suggestion.

## Built-in `man` Commands

`App` mounts `picle.models.MAN` automatically under `man`.

```text
picle#man tree
picle#man tree devices
picle#man json-schema
picle#man json-schema devices.cli
```

`man tree` prints a command tree and marks required fields, multiline fields, and dynamic dictionary keys.

`man json-schema` prints JSON schema for the root model or for a dotted path.

Notes:

- Dotted paths use field names, aliases, or serialization aliases.
- `man tree` requires Rich to render the tree.
- `man json-schema` is useful when you want to expose the shell structure as machine-readable data.
