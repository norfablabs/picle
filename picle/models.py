import json
import pprint
import logging
import os
import shutil
import difflib

from enum import Enum
from typing import List, Union, Optional, Callable, Any, get_args, get_origin, Dict
from pathlib import Path
from pydantic import BaseModel, StrictStr, Field, StrictBool, StrictInt, create_model
from pydantic.fields import FieldInfo
from pydantic_core import PydanticOmit, core_schema
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic._internal._model_construction import ModelMetaclass
from collections.abc import Mapping
from numbers import Number

log = logging.getLogger(__name__)

try:
    import yaml

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    import tabulate as tabulate_lib

    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False

try:
    from rich.console import Console as rich_console
    from rich.table import Table as RICHTABLE
    from rich.tree import Tree as RICHTREE
    from rich.markdown import Markdown

    RICHCONSOLE = rich_console()
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# --------------------------------------------------------------------------------
# FILTERS
# --------------------------------------------------------------------------------


class Filters(BaseModel):
    include: Any = Field(
        None,
        description="Filter output by pattern inclusion",
        json_schema_extra={"function": "filter_include"},
    )
    exclude: Any = Field(
        None,
        description="Filter output by pattern exclusion",
        json_schema_extra={"function": "filter_exclude"},
    )
    last: StrictInt = Field(
        None,
        description="Return last N lines",
        json_schema_extra={"function": "filter_last"},
    )

    @staticmethod
    def filter_include(data: Any, include: Any = None) -> str:
        """
        Filter data line by line using provided pattern. Returns only lines that contain the requested include pattern.

        Args:
            data: Data to filter.
            include: Pattern to filter data.

        Returns:
            str: Filtered lines joined by newline.
        """
        include = str(include)
        return "\n".join([line for line in str(data).splitlines() if include in line])

    @staticmethod
    def filter_exclude(data: Any, exclude: Any = None) -> str:
        """
        Filter data line by line using provided pattern. Returns only lines that do not contain the requested exclude pattern.

        Args:
            data: Data to filter.
            exclude: Pattern to filter data.

        Returns:
            str: Filtered lines joined by newline.
        """
        exclude = str(exclude)
        return "\n".join(
            [line for line in str(data).splitlines() if exclude not in line]
        )

    @staticmethod
    def filter_last(data: Any, last: int = None) -> str:
        """
        Returns only the last N lines.

        Args:
            data: Data to filter.
            last: Number of lines to return from the end.

        Returns:
            str: Last N lines joined by newline.
        """
        lines = str(data).splitlines()
        return "\n".join(lines[-last:] if last else lines)


# --------------------------------------------------------------------------------
# OUTPUTTERS
# --------------------------------------------------------------------------------


class TabulateTableFmt(str, Enum):
    plain = "plain"
    simple = "simple"
    github = "github"
    grid = "grid"
    simple_grid = "simple_grid"
    rounded_grid = "rounded_grid"
    heavy_grid = "heavy_grid"
    mixed_grid = "mixed_grid"
    double_grid = "double_grid"
    fancy_grid = "fancy_grid"
    outline = "outline"
    simple_outline = "simple_outline"
    rounded_outline = "rounded_outline"
    heavy_outline = "heavy_outline"
    mixed_outline = "mixed_outline"
    double_outline = "double_outline"
    fancy_outline = "fancy_outline"
    pipe = "pipe"
    orgtbl = "orgtbl"
    asciidoc = "asciidoc"
    jira = "jira"
    presto = "presto"
    pretty = "pretty"
    psql = "psql"
    rst = "rst"
    mediawiki = "mediawiki"
    moinmoin = "moinmoin"
    youtrack = "youtrack"
    html = "html"
    unsafehtml = "unsafehtml"
    latex = "latex"
    latex_raw = "latex_raw"
    latex_booktabs = "latex_booktabs"
    latex_longtable = "latex_longtable"
    textile = "textile"
    tsv = "tsv"


class TabulateTableOutputter(BaseModel):
    """Outputter that formats data as a text table using the tabulate library."""

    tablefmt: TabulateTableFmt = Field(None, description="Table format")
    headers: Union[StrictStr, List[str]] = Field(None, description="Table headers")
    sortby: StrictStr = Field(None, description="Column name to sort by")
    reverse: StrictBool = Field(
        None,
        description="Reverse table order when doing sortby",
        json_schema_extra={"presence": True},
    )
    headers_exclude: Union[StrictStr, List[str]] = Field(
        None, description="List of headers to exclude", alias="headers-exclude"
    )
    showindex: StrictBool = Field(
        None,
        description="Show table rows indexes",
        json_schema_extra={"presence": True},
    )
    maxcolwidths: StrictInt = Field(
        None, description="Maximum width of the column before wrapping text"
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        return Outputters.outputter_tabulate_table(*args, **kwargs)


class RichTableOutputter(BaseModel):
    """Outputter that formats data as a Rich table."""

    title: Optional[StrictStr] = Field(None, description="Table title")
    headers: List[str] = Field(None, description="Table headers")
    sortby: Optional[StrictStr] = Field(None, description="Column name to sort by")

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        return Outputters.outputter_rich_table(*args, **kwargs)


class PprintOutputterModel(BaseModel):
    """Model for pretty-print outputter"""

    indent: StrictInt = Field(4, description="Indentation added for each nesting level")
    width: StrictInt = Field(80, description="Maximum number of characters per line")
    depth: StrictInt = Field(
        None, description="Maximum depth of nested structures to display"
    )
    compact: StrictBool = Field(
        False,
        description="Fit as many items as possible on each line",
        json_schema_extra={"presence": True},
    )
    sort_dicts: StrictBool = Field(
        True,
        description="Sort dictionary keys before display",
        alias="sort-dicts",
        json_schema_extra={"presence": True},
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        return Outputters.outputter_pprint(*args, **kwargs)


class NestedOutputterModel(BaseModel):
    """Model for nested outputter"""

    initial_indent: int = Field(
        0,
        description="Initial indentation level for nested output",
        alias="initial-indent",
    )
    with_tables: bool = Field(
        False,
        description="Whether to format output in nested tables",
        alias="with-tables",
        json_schema_extra={"presence": True},
    )
    tablefmt: TabulateTableFmt = Field(None, description="Table format")
    tabulate_kwargs: dict = Field(
        None,
        description="JSON string of additional keyword arguments for tabulate",
        alias="tabulate-kwargs",
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        if kwargs.get("tabulate_kwargs"):
            kwargs["tabulate_kwargs"] = json.loads(kwargs["tabulate_kwargs"])
        return Outputters.outputter_nested(*args, **kwargs)


class JsonOutputterModel(BaseModel):
    """Model for JSON outputter"""

    indent: StrictInt = Field(4, description="Indentation level for JSON output")
    sort_keys: StrictBool = Field(
        True,
        description="Sort dictionary keys in output",
        alias="sort-keys",
        json_schema_extra={"presence": True},
    )
    ensure_ascii: StrictBool = Field(
        True,
        description="Escape non-ASCII characters in output",
        alias="ensure-ascii",
        json_schema_extra={"presence": True},
    )
    separators: StrictStr = Field(
        None,
        description="Item and key separators as 'item_sep,key_sep' (e.g. ',: ' for compact output)",
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        if kwargs.get("separators"):
            parts = kwargs["separators"].split(",", 1)
            kwargs["separators"] = tuple(parts) if len(parts) == 2 else (parts[0], ":")
        return Outputters.outputter_json(*args, **kwargs)


class YamlOutputterModel(BaseModel):
    """Model for YAML outputter"""

    indent: StrictInt = Field(2, description="Indentation level for YAML output")
    absolute_indent: StrictInt = Field(
        0,
        description="Absolute indentation prepended to every output line",
        alias="absolute-indent",
    )
    sort_keys: StrictBool = Field(
        True,
        description="Sort dictionary keys in output",
        alias="sort-keys",
        json_schema_extra={"presence": True},
    )
    allow_unicode: StrictBool = Field(
        True,
        description="Allow Unicode characters instead of escaping them",
        alias="allow-unicode",
        json_schema_extra={"presence": True},
    )
    width: StrictInt = Field(None, description="Maximum line width before wrapping")
    default_flow_style: StrictBool = Field(
        False,
        description="Use flow style for collections",
        alias="default-flow-style",
        json_schema_extra={"presence": True},
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        return Outputters.outputter_yaml(*args, **kwargs)


class KvOutputterModel(BaseModel):
    """Model for key-value outputter"""

    separator: StrictStr = Field(
        ".", description="Separator used between nested key path segments"
    )

    class PicleConfig:
        pipe = "picle.models.PipeFunctionsModel"

    @staticmethod
    def run(*args: list, **kwargs: dict):
        return Outputters.outputter_kv(*args, **kwargs)


class Outputters(BaseModel):
    pprint: PprintOutputterModel = Field(
        None,
        description="Convert results to pretty string",
    )
    json_: JsonOutputterModel = Field(
        None,
        description="Print JSON string",
        alias="json",
    )
    yaml: YamlOutputterModel = Field(
        None,
        description="Print YAML output",
    )
    markdown: Any = Field(
        None,
        description="Print markdown text to terminal",
        json_schema_extra={"function": "outputter_rich_markdown", "outputter": True},
        alias="markdown",
    )
    nested: NestedOutputterModel = Field(
        None, description="Print data in nested format"
    )
    save: StrictStr = Field(
        None,
        description="Save results to a file",
        json_schema_extra={"function": "outputter_save"},
    )
    table: TabulateTableOutputter = Field(
        None,
        description="Format results as a table",
        json_schema_extra={"function": "outputter_tabulate_table", "outputter": True},
    )
    rich_table: RichTableOutputter = Field(
        None,
        description="Print table output using Rich",
        json_schema_extra={"function": "outputter_rich_table", "outputter": True},
        alias="rich-table",
    )
    kv: KvOutputterModel = Field(
        None,
        description="Convert dictionary result to Key-Value string",
    )

    @staticmethod
    def outputter_kv(data: dict, parent_key="", separator=".", is_top=True) -> str:
        """
        Turn a nested structure (combination of lists/dictionaries) into a
        flattened dictionary.

        This function is useful to explore deeply nested structures.
        """
        items = []
        if isinstance(data, dict):
            for key, value in data.items():
                new_key = (
                    "{}{}{}".format(parent_key, separator, key) if parent_key else key
                )
                items.extend(
                    Outputters.outputter_kv(
                        value, new_key, separator, is_top=False
                    ).items()
                )
        elif isinstance(data, list):
            for k, v in enumerate(data):
                new_key = "{}{}{}".format(parent_key, separator, k) if parent_key else k
                items.extend(
                    Outputters.outputter_kv(
                        {str(new_key): v}, separator=separator, is_top=False
                    ).items()
                )
        else:
            items.append((parent_key, data))

        if is_top:
            return "\n".join(f"{k}: {v}" if k else v for k, v in items)
        else:
            return dict(items)

    @staticmethod
    def outputter_pprint(
        data: Any,
        indent: int = 4,
        width: int = 80,
        depth: int = None,
        compact: bool = False,
        sort_dicts: bool = True,
    ) -> str:
        """
        Pretty-print results using Python's pprint module.

        Args:
            data: Any data to pretty-print.
            indent (int): Indentation added for each nesting level.
            width (int): Maximum number of characters per line.
            depth (int): Maximum depth of nested structures to display.
            compact (bool): Fit as many items as possible on each line.
            sort_dicts (bool): Sort dictionary keys before display.

        Returns:
            str: Nicely formatted string representation.
        """
        if isinstance(data, str):
            return data
        return pprint.pformat(
            data,
            indent=indent,
            width=width,
            depth=depth,
            compact=compact,
            sort_dicts=sort_dicts,
        )

    @staticmethod
    def outputter_nested(
        data: Union[dict, list],
        initial_indent: int = 0,
        with_tables: bool = False,
        tablefmt: str = "simple",
        tabulate_kwargs: dict = None,
    ) -> str:
        """
        Recursively formats and prints nested data structures (dictionaries and lists) in a human-readable format.

        Args:
            data (dict or list): Nested data structure to be formatted and printed.
            initial_indent (int): Initial indentation level.
            with_tables (bool): If True, will format flat lists as Tabulate tables.
            tablefmt (str): table format to use
            tabulate_kwargs (dict, optional): Arguments for tabulate table outputter.

        Returns:
            str: Formatted nested string.
        """
        tabulate_kwargs = tabulate_kwargs or {"tablefmt": tablefmt}

        key_styles = {
            1: "bold green",
            2: "bold blue",
            3: "bold yellow",
            4: "bold magenta",
        }

        def is_dictionary_list(data):
            for item in data:
                if not isinstance(item, Mapping):
                    return False
                for k, v in item.items():
                    if isinstance(v, Mapping):
                        return False
                    if isinstance(
                        v,
                        (
                            list,
                            tuple,
                        ),
                    ):
                        # see if inner list is a flat list of strings or integers;
                        # if so, greedily pack items onto lines of up to 20 chars,
                        # joining items on the same line with ", " and separating
                        # lines with "\n". A single item that exceeds 20 chars is
                        # placed on its own line without truncation.
                        if all(isinstance(i, (str, int, float)) for i in v):
                            lines, current, current_len = [], [], 0
                            for inner_v in v:
                                s = str(inner_v)
                                if not current:
                                    current, current_len = [s], len(s)
                                elif current_len + 2 + len(s) <= 20:
                                    current.append(s)
                                    current_len += 2 + len(s)
                                else:
                                    lines.append(", ".join(current))
                                    current, current_len = [s], len(s)
                            if current:
                                lines.append(", ".join(current))
                            item[k] = "\n".join(lines)
                        else:
                            return False
            return True

        def ustring(indent, msg, prefix="", suffix=""):
            indent *= " "
            fmt = "{0}{1}{2}{3}"
            return fmt.format(indent, prefix, msg, suffix)

        def style_key(key, level):
            key = str(key)
            style = key_styles.get(level)
            if HAS_RICH and style:
                return f"[{style}]{key}[/{style}]"
            return key

        def nest(ret, indent, prefix, out, key_level=0):
            if isinstance(ret, bytes):
                try:
                    ret = ret.decode("utf-8")
                except UnicodeDecodeError:
                    ret = str(ret)

            if ret is None or ret is True or ret is False:
                out.append(ustring(indent, ret, prefix=prefix))
            elif isinstance(ret, Number):
                out.append(ustring(indent, repr(ret), prefix=prefix))
            elif isinstance(ret, str):
                first_line = True
                for line in ret.splitlines():
                    line_prefix = " " * len(prefix) if not first_line else prefix
                    out.append(ustring(indent, line, prefix=line_prefix))
                    first_line = False
            elif isinstance(ret, (list, tuple)):
                # make a text table if it is a flat list
                if ret and with_tables and is_dictionary_list(ret):
                    table = Outputters.outputter_tabulate_table(ret, **tabulate_kwargs)
                    nest(table, indent + 2, prefix, out, key_level)
                else:
                    for ind in ret:
                        if isinstance(ind, (list, tuple, Mapping)):
                            out.append(ustring(indent, "|_"))
                            prefix = "" if isinstance(ind, Mapping) else "- "
                            nest(ind, indent + 2, prefix, out, key_level)
                        else:
                            nest(ind, indent, "- ", out, key_level)
            elif isinstance(ret, Mapping):
                # make a text table if it is a flat dict
                if ret and with_tables and is_dictionary_list([ret]):
                    table = Outputters.outputter_tabulate_table(
                        [ret], **tabulate_kwargs
                    )
                    nest(table, indent + 2, prefix, out, key_level)
                else:
                    if indent:
                        out.append(ustring(indent, "----------"))

                    for key in ret.keys():
                        val = ret[key]
                        styled_key = style_key(key, key_level + 1)
                        out.append(
                            ustring(indent, styled_key, suffix=":", prefix=prefix)
                        )
                        # Dict depth controls key coloring; list depth does not.
                        nest(val, indent + 4, "", out, key_level + 1)

            return out

        # make sure data is sorted
        try:
            if isinstance(data, dict):
                data = dict(sorted(data.items()))
            elif isinstance(data, list):
                if data and isinstance(data[0], dict):
                    first_key = next(iter(data[0]))
                    data = list(sorted(data, key=lambda x: x.get(first_key, "")))
                else:
                    data = list(sorted(data))
        except Exception as e:
            log.warning(f"Nested outputter data sorting failed: '{e}'")

        lines = nest(data, initial_indent, "", [], key_level=0)
        lines = "\n".join(lines)

        return lines

    @staticmethod
    def outputter_rich_table(
        data: list[dict], headers: list = None, title: str = None, sortby: str = None
    ) -> Any:
        """
        Format a list of dictionaries as a Rich table.

        Args:
            data (list[dict]): List of dictionaries to display.
            headers (list, optional): Column headers; defaults to the keys of the first row.
            title (str, optional): Table title.
            sortby (str, optional): Key name to sort rows by.

        Returns:
            Any: A Rich Table object, or the original data if Rich is unavailable.
        """
        if not HAS_RICH or not isinstance(data, list):
            return data

        if not data:
            return data

        headers = headers or list(data[0].keys())
        table = RICHTABLE(title=title, box=False)

        # add table columns
        for h in headers:
            table.add_column(h, justify="left", no_wrap=True)

        # sort the table
        if sortby:
            sorted_data = sorted(data, key=lambda d: d[sortby])
        else:
            sorted_data = data

        # add table rows
        for item in sorted_data:
            cells = [str(item.get(h, "")) for h in headers]
            table.add_row(*cells)

        return table

    @staticmethod
    def outputter_yaml(
        data: Union[dict, list, bytes],
        absolute_indent: int = 0,
        indent: int = 2,
        sort_keys: bool = True,
        allow_unicode: bool = True,
        width: int = None,
        default_flow_style: bool = False,
    ) -> Any:
        """
        Format structured data as a YAML string.

        Args:
            data (dict, list, or bytes): Data to print.
            absolute_indent (int): Indentation to prepend for entire output.
            indent (int): Indentation for YAML output.
            sort_keys (bool): Sort dictionary keys in output.
            allow_unicode (bool): Allow Unicode characters instead of escaping them.
            width (int): Maximum line width before wrapping.
            default_flow_style (bool): Use flow style for collections.

        Returns:
            Any: YAML-formatted string or error message.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        if isinstance(data, str):
            return data

        # data should be a YAML string
        try:
            if HAS_YAML:
                data = yaml.safe_dump(
                    data,
                    default_flow_style=default_flow_style,
                    sort_keys=sort_keys,
                    indent=indent,
                    allow_unicode=allow_unicode,
                    width=width,
                )
                # add indent
                if absolute_indent:
                    data = "\n".join(
                        [f"{' ' * absolute_indent}{i}" for i in data.splitlines()]
                    )
            else:
                log.error(
                    "PICLE YAML outputter yaml library import failed, install: pip install pyyaml"
                )
        except Exception as e:
            print(
                f"ERROR: Failed to format data as YAML string:\n{data}\n\nError: '{e}'"
            )

        return data

    @staticmethod
    def outputter_json(
        data: Union[dict, list, bytes],
        indent: int = 4,
        sort_keys: bool = True,
        ensure_ascii: bool = True,
        separators: tuple = None,
    ) -> Any:
        """
        Pretty print JSON string.

        Args:
            data (dict, list, or bytes): Data to print.
            indent (int): Indentation for JSON output.
            sort_keys (bool): Sort dictionary keys in output.
            ensure_ascii (bool): Escape non-ASCII characters in output.
            separators (tuple): Item and key separators, e.g. (',', ': ').

        Returns:
            Any: JSON-formatted string or error message.
        """
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        if isinstance(data, str):
            return data

        # data should be a json string
        try:
            data = json.dumps(
                data,
                indent=indent,
                sort_keys=sort_keys,
                ensure_ascii=ensure_ascii,
                separators=separators,
            )
        except Exception as e:
            print(
                f"ERROR: Failed to format data as JSON string:\n{data}\n\nError: '{e}'"
            )

        return data

    @staticmethod
    def outputter_rich_markdown(data: Any) -> Any:
        """
        Print markdown output using Rich library.

        Args:
            data: Any data to print.

        Returns:
            Any: Rich Markdown object or string.
        """
        if not isinstance(data, str):
            data = str(data)

        if HAS_RICH:
            return Markdown(data)
        else:
            return data

    @staticmethod
    def outputter_save(data: Any, save: str) -> Any:
        """
        Output data into a file.

        Args:
            data: Any data to print.
            save (str): File path to save data.

        Returns:
            Any: The data that was saved.
        """
        # create directories
        abspath = os.path.abspath(save)
        dirs = os.path.split(abspath)[0]
        os.makedirs(dirs, exist_ok=True)

        # save data to file
        with open(save, "w") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                f.write(str(data))

        return data

    @staticmethod
    def outputter_tabulate_table(
        data: list,
        headers_exclude: list = None,
        sortby: str = None,
        reverse: bool = False,
        tablefmt: str = "grid",
        headers: list = None,
        showindex: bool = True,
        maxcolwidths: int = None,
    ) -> Any:
        """
        Format and output data as a text table using the tabulate library.

        Args:
            data (list): A list of dictionaries or list of lists to be formatted into a table. If it is a list of lists, the function merges nested lists.
            headers_exclude (list, optional): A list or comma-separated string of headers to exclude from the table.
            sortby (str, optional): The key name to sort the table by. If None, no sorting is applied.
            reverse (bool, optional): If True, reverses the sort order. Defaults to False.
            tablefmt (str): Table format style.
            headers (list or str, optional): Specifies the table headers. Can be a list, a comma-separated string, or 'keys' to use dictionary keys as headers.
            showindex (bool, optional): If True, includes an index column in the table.
            maxcolwidths (int, optional): Maximum width of the column before wrapping text.

        Returns:
            Any: Tabulated table string or error message.
        """
        if not HAS_TABULATE:
            log.error(
                "PICLE Table outputter tabulate library import failed, install: pip install tabulate"
            )
            return data
        if not isinstance(data, list):
            log.error("PICLE Table outputter data is not a list")
            return data

        # transform headers to exclude argument
        headers_exclude = headers_exclude or []
        if isinstance(headers_exclude, str) and "," in headers_exclude:
            headers_exclude = [i.strip() for i in headers_exclude.split(",")]

        # form base tabulate arguments
        if isinstance(headers, str):
            headers = [i.strip() for i in headers.split(",")]
        elif headers is None:
            headers = "keys"

        tabulate_kw = {
            "headers": headers,
            "tablefmt": tablefmt,
            "maxcolwidths": maxcolwidths,
        }

        # form singe table out of list of lists
        table_ = []
        while data:
            item = data.pop(0)
            if isinstance(item, list):
                table_.extend(item)
            else:
                table_.append(item)
        data = table_

        # sort results
        if sortby:
            data = sorted(
                data,
                reverse=reverse,
                key=lambda item: str(item.get(sortby, "")),
            )

        # filter table headers if requested to do so
        if headers_exclude:
            data = [
                {k: v for k, v in res.items() if k not in headers_exclude}
                for res in data
            ]

        # transform data content to match headers
        if isinstance(tabulate_kw["headers"], list):
            data = [[item.get(i, "") for i in tabulate_kw["headers"]] for item in data]

        # start index with 1 instead of 0
        if showindex is True:
            showindex = range(1, len(data) + 1)
            tabulate_kw["showindex"] = showindex

        return tabulate_lib.tabulate(data, **tabulate_kw)


class PipeFunctionsModel(Filters, Outputters):
    """
    Collection of common pipe functions to use in PICLE shell models
    """

    class PicleConfig:
        pipe = "self"


# --------------------------------------------------------------------------------
# MAN / DOC
# --------------------------------------------------------------------------------


class MAN(BaseModel):
    """
    Manual and documentation related functions
    """

    tree: Optional[StrictStr] = Field(
        None,
        description="Print commands tree for shell model specified by dot separated path e.g. model.shell.command",
        json_schema_extra={"function": "print_model_tree"},
    )
    json_schema: Optional[StrictStr] = Field(
        None,
        description="Print json schema for shell model specified by dot separated path e.g. model.shell.command",
        json_schema_extra={"function": "print_model_json_schema"},
        alias="json-schema",
    )

    @staticmethod
    def _construct_model_tree(model, tree: RICHTREE, path: list) -> RICHTREE:
        """
        Recursively construct a Rich tree for a shell model.

        Args:
            model: Model or model class to construct tree for.
            tree (RICHTREE): Rich tree object to add nodes to.
            path (list): Path to traverse for nested models.

        Returns:
            RICHTREE: The constructed Rich tree.
        """
        model_cls = model if isinstance(model, type) else type(model)
        for field_name, field in model_cls.model_fields.items():
            if (
                path
                and field_name != path[0]
                and field.alias != path[0]
                and field.serialization_alias != path[0]
            ):
                continue
            flags = ""
            json_schema_extra = field.json_schema_extra or {}
            # form tree element label
            label = [
                f"[bold]{field.alias or field.serialization_alias or field_name}__FLAGS__:[/bold]"
            ]
            if field.is_required():
                flags += "R"
            if json_schema_extra.get("multiline"):
                flags += "M"
            if field.description:
                label[0] += f"    {field.description}"
            if field.get_default() is not None and field.annotation != Callable:
                default_value = field.get_default()
                if isinstance(
                    default_value, (str, int, float, bool, list, dict, tuple, set)
                ):
                    label.append(f"default '{field.get_default()}'")
            if field.examples:
                examples = (
                    field.examples
                    if isinstance(field.examples, list)
                    else [field.examples]
                )
                examples = [str(e) for e in examples]
                label.append(f"examples: {', '.join(examples)}")
            if flags:
                label[0] = label[0].replace("__FLAGS__", f" ({flags})")
            else:
                label[0] = label[0].replace("__FLAGS__", "")
            next_tree = tree.add(", ".join(label))
            # handle dynamic dictionary tree - Dict[str, NestedModel] with "pkey" in json_schema_extra
            if get_origin(field.annotation) in (dict, Dict) and json_schema_extra.get(
                "pkey"
            ):
                # add dynamic key info to the tree
                key_name = json_schema_extra["pkey"]
                key_desc = json_schema_extra.get("pkey_description", "Input key")
                next_tree.add(f"[bold]{key_name} (D):[/bold]    {key_desc}")
                # recurse to nested model for dynamic dictionary values
                nested_model = get_args(field.annotation)[1]
                MAN._construct_model_tree(nested_model, next_tree, path[1:])
            # recurse to next level model
            elif isinstance(field.annotation, ModelMetaclass):
                MAN._construct_model_tree(field.annotation, next_tree, path[1:])

        return tree

    @staticmethod
    def print_model_tree(root_model: object, **kwargs: dict) -> None:
        """
        Print model tree for shell model specified by dot separated path (e.g. model.shell.command).

        Args:
            root_model: PICLE App root model to print tree for.
            **kwargs: Additional keyword arguments (expects 'tree' for path).
        """
        if HAS_RICH:
            RICHCONSOLE.print(
                "\n[bold]R[/bold] - required field, "
                + "[bold]M[/bold] - supports multiline input, "
                + "[bold]D[/bold] - dynamic key\n"
            )
            path = kwargs["tree"].split(".") if kwargs.get("tree") else []
            rich_tree = RICHTREE("[bold]root[/bold]")
            RICHCONSOLE.print(
                MAN._construct_model_tree(
                    model=root_model.model_construct(), tree=rich_tree, path=path
                )
            )
        else:
            log.error(
                "PICLE model tree outputter requires Rich library, install: pip install rich"
            )

    @staticmethod
    def _recurse_to_model(model, path: list) -> ModelMetaclass:
        """
        Recurse to model specified by dot separated path (e.g. model.shell.command).

        Args:
            model: Model to recurse through.
            path (list): Path to recurse to.

        Returns:
            ModelMetaclass: The model at the specified path.
        """
        if not path:
            return model

        for field_name, field in (
            model if isinstance(model, type) else type(model)
        ).model_fields.items():
            if (
                field_name == path[0]
                or field.alias == path[0]
                or field.serialization_alias == path[0]
            ):
                # recurse to next level model
                if isinstance(field.annotation, ModelMetaclass):
                    return MAN._recurse_to_model(field.annotation, path[1:])

        return model

    @staticmethod
    def print_model_json_schema(root_model: object, **kwargs: dict) -> str:
        """
        Print model JSON schema for shell model specified by dot separated path (e.g. model.shell.command).

        Args:
            root_model: PICLE App root model to print JSON schema for.
            **kwargs: Additional keyword arguments (expects 'json_schema' for path).

        Returns:
            str: JSON schema as a formatted string.
        """

        class MyGenerateJsonSchema(GenerateJsonSchema):
            def handle_invalid_for_json_schema(
                self, schema: core_schema.CoreSchema, error_info: str
            ) -> JsonSchemaValue:
                raise PydanticOmit

            def callable_schema(self, schema):
                print(schema)
                raise PydanticOmit

            def render_warning_message(kind, detail: str) -> None:
                print(kind, detail)

        path = kwargs["json_schema"].split(".") if kwargs.get("json_schema") else []
        model = MAN._recurse_to_model(root_model, path=path)
        return json.dumps(
            model.model_json_schema(schema_generator=MyGenerateJsonSchema),
            indent=4,
            sort_keys=True,
        )


# --------------------------------------------------------------------------------
# CONFIGURATION MODEL
# --------------------------------------------------------------------------------


class ConfigModelShowCommands(BaseModel):
    configuration: Any = Field(
        None,
        description="Show running configuration content",
        json_schema_extra={"function": "show_config"},
    )
    changes: Any = Field(
        None,
        description="Show uncommitted changes diff between temp and running config",
        json_schema_extra={"function": "show_changes"},
    )

    @staticmethod
    def show_config(shell_command: list) -> dict:
        """
        Load and return the running configuration.

        Args:
            shell_command (list): The shell command context.

        Returns:
            dict: Configuration content dictionary.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        return ConfigModel.load_config(config_file)

    @staticmethod
    def show_changes(shell_command: list) -> str:
        """
        Show diff between saved config and uncommitted temp config.

        Args:
            shell_command (list): The shell command context.

        Returns:
            str: Unified diff string.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"

        if not Path(temp_file).exists():
            return "No uncommitted changes"

        saved_content = ConfigModel.load_config(config_file)
        temp_content = ConfigModel.load_config(temp_file)

        saved_lines = yaml.safe_dump(
            saved_content, default_flow_style=False, sort_keys=True, indent=2
        ).splitlines(keepends=True)
        temp_lines = yaml.safe_dump(
            temp_content, default_flow_style=False, sort_keys=True, indent=2
        ).splitlines(keepends=True)

        diff = difflib.unified_diff(
            saved_lines, temp_lines, fromfile=config_file, tofile=temp_file
        )
        result = "".join(diff)

        return result if result else "No differences found"

    class PicleConfig:
        pipe = PipeFunctionsModel
        outputter = Outputters.outputter_nested


# Fields managed internally by ConfigModel, excluded from negate model mirroring
_CONFIG_MODEL_MANAGED_FIELDS = frozenset(
    {"show", "commit", "rollback", "erase_configuration", "clear_changes", "no"}
)


class ConfigModel(BaseModel):
    """
    Base class for configuration management models.

    This class provides functionality to:

    - Load configuration from YAML files
    - Update nested configuration values through PICLE commands
    - Stage changes in a temp file before committing
    - Save committed configuration with rotating backups
    - Rollback to previous configuration versions

    Usage:
        1. Define your config structure as nested Pydantic models
        2. Create a config manager that inherits from ConfigModel
        3. Set config_file path via PicleConfig
        4. Use PICLE commands to update config values (staged in temp file)
        5. Use 'commit' to persist or 'clear-changes' to discard
    """

    show: ConfigModelShowCommands = Field(None, description="Show commands")
    commit: StrictBool = Field(
        None,
        description="Commit pending config changes",
        json_schema_extra={"function": "commit_config", "presence": True},
    )
    rollback: StrictInt = Field(
        None,
        description="Rollback to a backup version",
        json_schema_extra={"function": "rollback_config"},
    )
    erase_configuration: StrictBool = Field(
        None,
        description="Erase running configuration",
        json_schema_extra={"function": "erase_config", "presence": True},
        alias="erase-configuration",
    )
    clear_changes: StrictBool = Field(
        None,
        description="Discard uncommitted changes",
        json_schema_extra={"function": "clear_changes_config", "presence": True},
        alias="clear-changes",
    )

    class PicleConfig:
        config_file: str = "configuration.yaml"  # Default config file path
        backup_on_save: int = (
            5  # Number of backups history to keep (set to 0 to disable)
        )
        commit_hook: Optional[Callable] = None  # Optional function to call after commit

    @staticmethod
    def load_config(config_file: str) -> dict:
        """
        Load configuration from YAML file.

        Args:
            config_file (str): Path to the configuration file.

        Returns:
            dict: Loaded configuration dictionary.
        """
        if not HAS_YAML:
            raise RuntimeError("PyYAML is required for config file operations")

        config_path = Path(config_file)

        if not config_path.exists():
            # Create directories and file if they don't exist
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.touch(exist_ok=True)
            log.info(f"Created config file: {config_file}")
            config_data = {}
        else:
            with open(config_path, "r", encoding="utf-8") as f:
                config_data = yaml.safe_load(f) or {}

        return config_data

    @staticmethod
    def save_config(
        config_file: str, config_data: dict, backup_on_save: int = 5
    ) -> str:
        """
        Save configuration to YAML file with rotating backups.

        Args:
            config_file (str): Path to the configuration file.
            config_data (dict): Configuration dictionary to save.
            backup_on_save (int): Number of backup files to keep (0 to disable).

        Returns:
            str: Status message.
        """
        config_path = Path(config_file)

        # Create rotating backups if requested
        if backup_on_save and config_path.exists():
            # Remove the oldest backup if it exists
            oldest_backup = Path(f"{config_path}.old{backup_on_save}")
            if oldest_backup.exists():
                os.remove(oldest_backup)
                log.debug(f"Removed oldest backup: {oldest_backup}")

            # Rotate existing backups (old1 -> old2, old2 -> old3, etc.)
            for i in range(backup_on_save - 1, 0, -1):
                old_backup = Path(f"{config_path}.old{i}")
                new_backup = Path(f"{config_path}.old{i + 1}")
                if old_backup.exists():
                    shutil.move(str(old_backup), str(new_backup))
                    log.debug(f"Rotated backup: {old_backup} -> {new_backup}")

            # Create new .old1 backup from current file
            newest_backup = Path(f"{config_path}.old1")
            shutil.copy2(config_path, newest_backup)
            log.debug(f"Created new backup: {newest_backup}")

        # Save the new configuration
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config_data, f, default_flow_style=False, sort_keys=True, indent=2
            )

        log.info(f"Saved config to {config_file}")

        return f"Saved config to {config_file}"

    @staticmethod
    def update_nested_value(data: dict, path: list, value: Any) -> dict:
        """
        Set a value in nested dictionary using path list.

        Args:
            data (dict): Dictionary to modify.
            path (list): List of keys representing the path.
            value: Value to set at the path.

        Returns:
            dict: Modified dictionary.
        """
        if not path:
            return data

        current = data
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            elif not isinstance(current[key], dict):
                log.warning(
                    f"Cannot traverse path: {'.'.join(path)}, {key} is not a dict"
                )
                return data
            current = current[key]

        # If both current value and new value are dicts, merge them
        if isinstance(value, dict) and isinstance(current.get(path[-1]), dict):
            current[path[-1]] = {**current[path[-1]], **value}
        # If both current value and new value are lists, extend the list
        elif isinstance(value, list) and isinstance(current.get(path[-1]), list):
            current[path[-1]].extend(value)
        else:
            current[path[-1]] = value
        return data

    @staticmethod
    def delete_nested_value(data: dict, path: list) -> dict:
        """
        Delete a key from a nested dictionary using a path list.

        Args:
            data (dict): Dictionary to modify.
            path (list): List of keys representing the path to the key to delete.

        Returns:
            dict: Modified dictionary.
        """
        if not path:
            return data

        current = data
        for key in path[:-1]:
            if not isinstance(current, dict) or key not in current:
                log.warning(
                    f"Cannot traverse path for deletion: "
                    f"'{'.'.join(str(k) for k in path)}', key '{key}' not found"
                )
                return data
            current = current[key]

        if isinstance(current, dict) and path[-1] in current:
            del current[path[-1]]
            log.debug(
                f"Deleted key '{path[-1]}' at path "
                f"'{'.'.join(str(k) for k in path[:-1])}'"
            )
        else:
            log.warning(
                f"Key '{path[-1]}' not found at path "
                f"'{'.'.join(str(k) for k in path[:-1])}'"
            )

        return data

    @staticmethod
    def get_command_path(command: list) -> list:
        """
        Extract the configuration path from parsed command segments.

        Args:
            command (list): List of parsed command segment dicts.

        Returns:
            list: List of string path components.
        """
        ret = []
        for item in command:
            if isinstance(item["parameter"], str):
                ret.append(item["parameter"])

        return ret

    @staticmethod
    def get_model_config(shell_command: list) -> dict:
        """
        Reconstruct model configuration by merging ConfigModel defaults with the command's root model PicleConfig.

        Args:
            shell_command (list): The shell command context.

        Returns:
            dict: Merged configuration dictionary.
        """
        command_root_model = shell_command[0]["model"]

        # reconstruct model configuration
        model_config = {
            k: v
            for k, v in ConfigModel.PicleConfig.__dict__.items()
            if not k.startswith("_")
        }
        model_config.update(
            {
                k: v
                for k, v in command_root_model.PicleConfig.__dict__.items()
                if not k.startswith("_")
            }
        )
        return model_config

    @staticmethod
    def erase_config(shell_command: list, erase_configuration: bool = True) -> str:
        """
        Erase configuration and save empty config to temp file.

        Args:
            shell_command (list): The shell command context.
            erase_configuration (bool): Presence flag (always True when invoked).

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.safe_dump({}, f, default_flow_style=False, sort_keys=True, indent=2)

        return "Configuration cleared (uncommitted). Use 'commit' to save or 'show changes' to review."

    @staticmethod
    def clear_changes_config(shell_command: list, clear_changes: bool = True) -> str:
        """
        Discard uncommitted changes by deleting the temp config file.

        Args:
            shell_command (list): The shell command context.
            clear_changes (bool): Presence flag (always True when invoked).

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"

        if not os.path.exists(temp_file):
            return "No uncommitted changes to discard"

        os.remove(temp_file)
        return "Uncommitted changes discarded"

    @staticmethod
    def commit_config(shell_command: list, commit: bool = True) -> str:
        """
        Commit pending changes - save temp config to the main config file and remove temp.

        Args:
            shell_command (list): The shell command context.
            commit (bool): Presence flag (always True when invoked).

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        backup_on_save = model_config.get("backup_on_save", 5)
        temp_file = config_file + ".tmp"

        if not Path(temp_file).exists():
            return "No uncommitted changes to commit"

        temp_content = ConfigModel.load_config(temp_file)
        ConfigModel.save_config(
            config_file, temp_content, backup_on_save=backup_on_save
        )
        os.remove(temp_file)

        if model_config.get("commit_hook"):
            try:
                model_config["commit_hook"]()
            except Exception as e:
                log.error(f"Commit hook execution failed: {e}")
                return f"Configuration committed with errors in commit hook: {e}"

        return "Configuration committed successfully"

    @staticmethod
    def rollback_config(shell_command: list, rollback: int) -> str:
        """
        Rollback to a backup version by loading .oldN file into temp config.

        Args:
            shell_command (list): The shell command context.
            rollback (int): Backup number to rollback to (1, 2, 3, ...).

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"
        backup_file = f"{config_file}.old{rollback}"

        if not Path(backup_file).exists():
            return f"Backup file not found: {backup_file}"

        backup_content = ConfigModel.load_config(backup_file)

        # save backup content to temp file for review before commit
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                backup_content, f, default_flow_style=False, sort_keys=True, indent=2
            )

        return f"Loaded backup {backup_file} into temp config. Use 'commit' to apply or 'show changes' to review."

    @staticmethod
    def run(shell_command: list, **kwargs: dict) -> str:
        """
        Run method for configuration operations. Saves changes to a temp file. Use 'commit' to persist to config file.

        Args:
            shell_command (list): The shell command that triggered this run method.
            **kwargs: Field values collected from the command line.

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        command_path = ConfigModel.get_command_path(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"

        # load from temp file if it exists (accumulate changes), else from config file
        if Path(temp_file).exists():
            config_content = ConfigModel.load_config(temp_file)
        else:
            config_content = ConfigModel.load_config(config_file)

        # update configuration data
        ConfigModel.update_nested_value(config_content, command_path, kwargs)

        # save to temp file
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config_content, f, default_flow_style=False, sort_keys=True, indent=2
            )

        return "Configuration updated (uncommitted). Use 'commit' to save or 'show changes' to review."

    @staticmethod
    def _negate_run(shell_command: list, **kwargs: dict) -> str:
        """
        Run method for negation (deletion) operations. Removes keys from temp/config file.
        Use 'commit' to persist changes.

        Args:
            shell_command (list): The shell command that triggered this run method.
            **kwargs: Presence-flagged leaf fields indicating specific keys to remove.
                      If empty, the entire command path sub-tree is removed.

        Returns:
            str: Status message.
        """
        model_config = ConfigModel.get_model_config(shell_command)
        command_path = ConfigModel.get_command_path(shell_command)
        config_file = model_config["config_file"]
        temp_file = config_file + ".tmp"

        # Strip the leading 'no' token from the command path
        if command_path and command_path[0] == "no":
            command_path = command_path[1:]

        # Load config (prefer temp file to accumulate staged changes)
        if Path(temp_file).exists():
            config_content = ConfigModel.load_config(temp_file)
        else:
            config_content = ConfigModel.load_config(config_file)

        # Use the last model's explicitly collected field values to determine which
        # leaf keys to delete. This avoids treating VirtualDictModel key kwargs
        # (e.g. worker_name="worker1") as leaf fields - those are path components,
        # already incorporated into command_path by get_command_path.
        last_model_fields = shell_command[-1].get("fields", [])
        leaf_fields = [f["name"] for f in last_model_fields if f["values"] is not ...]

        if leaf_fields:
            for key in leaf_fields:
                ConfigModel.delete_nested_value(config_content, command_path + [key])
        elif command_path:
            ConfigModel.delete_nested_value(config_content, command_path)

        # Save to temp file
        with open(temp_file, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                config_content, f, default_flow_style=False, sort_keys=True, indent=2
            )

        return "Configuration negated (uncommitted). Use 'commit' to save or 'show changes' to review."

    @staticmethod
    def _build_negate_model(source_cls: type) -> type:
        """
        Recursively build a negation mirror model for *source_cls*.

        The resulting model has the same field tree as *source_cls* (minus the
        ConfigModel management fields) so that PICLE can provide full tab-completion
        for ``no <path>`` commands.  Leaf fields are given ``presence=True`` so they
        can be referenced without a value.  Nested model fields are recursively
        replaced with their own negate mirrors.  The model's ``run()`` delegates to
        ``ConfigModel._negate_run``.

        Args:
            source_cls (type): The ConfigModel subclass (or any nested BaseModel) to mirror.

        Returns:
            type: A dynamically created Pydantic model class.
        """
        field_definitions: dict = {}

        for field_name, field_info in source_cls.model_fields.items():
            if field_name in _CONFIG_MODEL_MANAGED_FIELDS:
                continue

            annotation = field_info.annotation
            extra = dict(field_info.json_schema_extra or {})

            # Common kwargs for the mirrored Field
            field_kwargs: dict = {
                "default": None,
                "description": field_info.description,
            }
            if field_info.alias:
                field_kwargs["alias"] = field_info.alias
            if field_info.serialization_alias:
                field_kwargs["serialization_alias"] = field_info.serialization_alias

            if isinstance(annotation, ModelMetaclass):
                # Nested Pydantic model – recurse
                nested_negate = ConfigModel._build_negate_model(annotation)
                field_kwargs["json_schema_extra"] = extra
                field_definitions[field_name] = (
                    nested_negate,
                    Field(**field_kwargs),
                )

            elif get_origin(annotation) is dict and extra.get("pkey"):
                # Dynamic-dictionary field (Dict[K, V] with pkey) – preserve the
                # pkey metadata so VirtualDictModel is still used for traversal.
                args = get_args(annotation)
                if len(args) > 1 and isinstance(args[1], ModelMetaclass):
                    nested_negate = ConfigModel._build_negate_model(args[1])
                    annotation = Dict[args[0], nested_negate]
                field_kwargs["json_schema_extra"] = extra
                field_definitions[field_name] = (
                    annotation,
                    Field(**field_kwargs),
                )

            else:
                # Scalar / leaf field – mark with presence so it can be referenced
                # without providing a value.
                extra.pop("function", None)
                extra["presence"] = True
                field_kwargs["json_schema_extra"] = extra
                field_definitions[field_name] = (
                    annotation,
                    Field(**field_kwargs),
                )

        NegateModel = create_model(
            f"Negate{source_cls.__name__}",
            **field_definitions,
        )
        NegateModel.run = staticmethod(ConfigModel._negate_run)
        return NegateModel

    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs: dict) -> None:
        """
        Automatically inject a ``no`` field into every ConfigModel subclass.

        Called by Pydantic **after** ``complete_model_class()`` so ``model_fields``
        is already fully populated when we build the negate mirror.

        The ``no`` field points to a dynamically built negation mirror of the
        subclass, enabling commands like::

            config interface eth0 ip 1.2.3.4   # sets a value
            config no interface eth0 ip        # removes it (with full completion)

        Args:
            cls: The newly defined subclass.
            **kwargs: Extra keyword arguments forwarded to ``super().__pydantic_init_subclass__``.
        """
        super().__pydantic_init_subclass__(**kwargs)

        # Build the dynamic negate mirror for this subclass
        negate_model = ConfigModel._build_negate_model(cls)

        # Inject directly into __pydantic_fields__ so model_fields reflects the
        # change immediately without needing model_rebuild (which does not
        # re-run set_model_fields and therefore ignores __annotations__ changes).
        no_field_info = FieldInfo(
            annotation=negate_model,
            default=None,
            description="Negate/remove configuration",
        )
        cls.__pydantic_fields__["no"] = no_field_info
        cls.__annotations__["no"] = negate_model
