# Multi-line Input

If a field enables multi-line input, the user can type the literal value `load-terminal` to start collection.

PICLE reads lines until EOF and uses the collected text (joined by `\n`) as the field value.
At an empty input prompt, press Ctrl+D to finish collection on Linux, macOS, or Windows.

```python
from typing import Any
from pydantic import BaseModel, Field, StrictStr


class NotesCommand(BaseModel):
    body: StrictStr = Field(
        None,
        description="Multi-line note body",
        json_schema_extra={"multiline": True},
    )
    title: Any = Field(None, description="Note title")

    @staticmethod
    def run(**kwargs):
        return kwargs


class Root(BaseModel):
    notes: NotesCommand = Field(
        None,
        description="Create a note",
    )
```

Help shows the `load-terminal` option when appropriate:

```
picle#notes body ?
 <'body' value>    Multi-line note body
 load-terminal     Collect value using multi line input mode
```

Invoking multi-line collection:

```
picle#notes body load-terminal
Enter lines and hit Ctrl+D to finish multi line input
line 1
line 2
<Ctrl+D>
```

The collected value is then validated and passed to your callable as a single string containing embedded newlines.
