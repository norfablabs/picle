# Subshells And Navigation

If a model sets `PicleConfig.subshell = True`, entering that model without arguments pushes it onto the shell stack and changes the prompt.

This makes large command trees easier to use because you can navigate once and then run shorter commands inside the subshell.

## Example Model

```python
from enum import Enum
from typing import List, Union
from pydantic import BaseModel, Field, StrictBool, StrictStr


class ConnectionPlugin(str, Enum):
    netmiko = "netmiko"
    napalm = "napalm"


class DeviceCli(BaseModel):
    commands: Union[StrictStr, List[StrictStr]] = Field(
        ..., description="CLI commands to send to devices"
    )
    plugin: ConnectionPlugin = Field("netmiko", description="Connection plugin name")
    add_details: StrictBool = Field(
        None,
        description="Show detailed output",
        json_schema_extra={"presence": True},
    )

    @staticmethod
    def run(**kwargs):
        return f"Called device cli, kwargs: {kwargs}"

    class PicleConfig:
        subshell = True
        prompt = "devices[cli]#"


class DeviceTools(BaseModel):
    cli: DeviceCli = Field(None, description="Send CLI commands to devices")

    class PicleConfig:
        subshell = True
        prompt = "devices#"


class Root(BaseModel):
    target: StrictStr = Field("lab", description="Device group")
    platform: StrictStr = Field("eos", description="Device platform")
    devices: DeviceTools = Field(None, description="Device commands")
```

## Entering A Subshell

```text
picle#devices cli
devices[cli]#commands "show clock" add_details
Called device cli, kwargs: {
    'target': 'lab',
    'platform': 'eos',
    'plugin': 'netmiko',
    'commands': 'show clock',
    'add_details': True
}
```

You can also enter intermediate shells:

```text
picle#devices
devices#
```

## Defaults Follow You

When you enter a subshell, PICLE keeps non-`None` defaults from the current shell path in `shell_defaults`.

In the example above, the command inside `devices[cli]#` inherits:

- `target = "lab"`
- `platform = "eos"`
- `plugin = "netmiko"`

That is why `commands "show clock"` is enough once you are already inside the CLI subshell.

Leaving the subshell with `exit` or resetting with `top` clears the inherited defaults appropriately.

## Built-in Navigation Commands

PICLE exposes several global shell commands:

- `exit`: leave the current subshell, or terminate if already at the top level.
- `top`: return to the root shell and reset the shell stack.
- `end`: terminate the application immediately.
- `pwd`: print the current shell path.
- `cls`: clear the terminal screen.
- `history`: print command history.

```text
devices[cli]#pwd
Root->DeviceTools->DeviceCli

devices[cli]#exit
devices#

devices#top
picle#
```

Notes:

- Interactive history uses the same persistent `prompt_toolkit` session on Linux, macOS, and Windows.
- `PicleConfig.history_file` selects the history file, and `history_length` limits the number of entries written when the shell exits.
- History output skips meta commands such as `help`, `history`, `exit`, and commands ending in `?`.
