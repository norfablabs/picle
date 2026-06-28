# 0.13.0

## CHANGES

1. Replaced `pyreadline3` with `prompt_toolkit` as PICLE's interactive line-editing backend. The new backend is used consistently on Windows, Linux, and macOS for terminal input, cursor movement, completion, and command history, while PICLE's existing parser and command dispatch remain unchanged.

## BUGS

1. Fixed Enter and newline rendering in the VS Code integrated terminal on Windows while retaining completion and persistent history.
2. Routed multi-line and chat sub-prompts through the persistent prompt session so Ctrl+D continues to signal EOF on Windows.

## ENHANCEMENTS

1. Added a persistent `PromptSession` completion adapter that reuses PICLE's existing `completenames()` and `completedefault()` behavior without changing parsing or command dispatch.
2. Added an interactive `?` key binding that displays contextual help immediately without submitting or changing the current command buffer. Each request preserves the visible command line above its help output, and pressing `?` twice shows verbose help.

---

# 0.12.2

## BUGS

1. Fixing python 3.14 + compatibility- factorized cmd.py and updated it to work with pyreadline3
2. Fixing handling of quoted json string like '["key": "valu"]'

## ENHANCEMENTS

1. Nested with table improved to handle lists of string or integer items, and simple dictionaries, converting them to tables of single row.

---

# 0.12.1

## BUGS

1. Fixing command validation handling to make sure if validation succeeds but no data returned its not blocking the command
2. Enhancing outputters handling for chat shell model
3. Fixing streaming mode newline handling for write method

---

# 0.12.0

## FEATURES

1. Adding new chat shell mode
2. Adding `do_shell` method to run OS shell commands

---

# 0.11.2

## CHANGES

1. Enhancing nested output to color code dictionary key levels if Rich in use

## FEATURES

1. Adding support for model `source_<field name>` method to accept `choice` argument that holds current variable value

## BUGS

1. Fixing handling of field source collection when has only one value for the variable

---

# 0.11.1

## FEATURES

1. Improving pipe handling back backtracing it to parents models, if `pipe` set to False on the model `PicleConfig`, backtracing disabled
2. Adding support negate `no` command to configuraiton model, negate arguments are dynamically constructed for every model
3. Adding `last` filter to pipe functions to return last N lines of output

## ENHANCEMENTS

1. Updating outputter_kv to support flatenning arbitrary nested structures .
2. Added dedicated model for each outputter with configurable arguments: 

  - `PprintOutputterModel` indent, width, depth, compact, sort-dicts
  - `JsonOutputterModel` indent, sort-keys, ensure-ascii, separators
  - `YamlOutputterModel` indent, absolute-indent, sort-keys, allow-unicode, width, default-flow-style
  - `KvOutputterModel` separator
  - `NestedOutputterModel` initial_indent, with_tables, tabulate_kwargs

---

# 0.11.0

## FEATURES

1. Adding commands history persistency across shells, added `picle_file` config attribute to indicate where to store commands, default is `picle_history.txt`
2. Support added to handle parsing of cli commands into dynamic dictionaries, added `pkey` and `pkey_description` config parameters to `json_schema_extra`

## CHANGES

1. Enhanced MAN model to output tree for dynamic dictionaries models
2. Changing history handling to use `pyreadline` module

---

# 0.10.1

## BUGS

1. MAN fixing examples output when examples are anything but string

## CHANGES

1. Making mandatory fields to be at the top of help output and in bold cursor
2. To invoke multiline input mode changing command from `input` to `load-terminal`

## FEATURES

1. Adding `history` command to output commands history, adding `history_length` PicleConfig class config attribute
2. Improving message back to a user for incorrect command with suggesting possible completions
3. Enhancing errors output printed to the screen by making it to be printed in red color

---

# 0.10.0

## CHANGES

1. Dependencies updates to loosen them up
2. Adding type hints throughout and updating doc strings
3. Fixed pydantic warnings about model_fields access and about using extra arguments on fields

## FEATURES

1. Added ConfigModel model to picle to help with maintaininng configuration files using Picle interactive shell.

## BUGS

1. __init__ ~L97 -PicleConfig accessed without hasattr guard — crash for models without it
2. do_help ~L855 - Multi-word help silently discarded — never printed
3. do_help ~L857 - Unhandled FieldLooseMatchOnly/FieldKeyError exceptions
4. print_model_help - Medium	width not computed for all lines keys — misaligned output
5. default ~L1004 - Partial alias match reports empty completions list
6. do_exit ~L872 - Missing PicleConfig guard on prompt access
7. do_top ~L883 - Same missing guard

---

# 0.9.3

## CHANGES

1. Improving outputter models handling

---

# 0.9.2

## CHANGES

1. Improved value conversion logic to not convert values to integers or bool etc if field annotation is `str` or `StrictStr`
2. Updated `pyproject.toml` file with dependency version for PyYAML and Tabulate modules

---

# 0.9.1

## FEATURES

1. Extending nested outputter with capability to include tables within nested output if data is a list of dictionaries

---

# 0.9.0

## CHANGES

1. Removed support for using `Callable` annotation for calling model method
2. Removed formatters from built in models, instead need to use outputter
3. Improved pipe functions handling logic 
4. Rich is now a default outputter, can be disabled using ``use_rich`` config parameter in the root's model PicleConfig 

## FEATURES

1. Added Tabulate table outputter
2. Added `save` outputter to save results into a file
3. Added support for pipe attribute to reference `path.to.pipemodel` Python import string
