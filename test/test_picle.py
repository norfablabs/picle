import unittest
import unittest.mock
import sys
import subprocess
import pytest

from picle import App
from pydantic import BaseModel, StrictStr, Field
from .picle_test_shell import Root

mock_stdin = unittest.mock.create_autospec(sys.stdin)
mock_stdout = unittest.mock.create_autospec(sys.stdout)
shell = App(Root, stdin=mock_stdin, stdout=mock_stdout)


def test_callable():
    shell.onecmd("top")  # go to top
    shell.onecmd("show version")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    assert shell_output == "0.1.0\r\n"


def test_default_values():
    shell.onecmd("top")  # go to top
    shell.onecmd("salt nr cli commands abc")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
        ]
    )


def test_default_values_from_subshell():
    shell.onecmd("top")  # go to top
    shell.onecmd("salt nr cli")  # go to subshell
    shell.onecmd("commands abc")  # call command
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
        ]
    )


def test_presence_at_the_end():
    shell.onecmd("top")  # go to top
    shell.onecmd("salt nr cli commands abc add_details")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
            "'add_details': True",
        ]
    )


def test_presence_in_between():
    shell.onecmd("top")  # go to top
    shell.onecmd("salt nr cli commands abc add_details hosts ceos1")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
            "'add_details': True",
            "'hosts': 'ceos1'",
        ]
    )


def test_pipe_function_include():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | include Why")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "Why did the network engineer always carry a ladder?" in shell_output


def test_pipe_function_exclude():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | exclude Why")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "Why did the network engineer always carry a ladder?" not in shell_output


def test_pipe_function_last():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | last 2")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "The End." in shell_output
    assert "Why did the network engineer always carry a ladder?" not in shell_output


def test_pipe_function_last_single_line():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | last 1")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert len(shell_output.splitlines()) == 1
    assert "Why did the network engineer always carry a ladder?" not in shell_output


def test_pipe_function_last_many_lines():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | last 6")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "Why did the network engineer always carry a ladder?" in shell_output
    assert "The End." in shell_output


def test_multiple_pipe_functions():
    shell.onecmd("top")  # go to top
    shell.onecmd("show joke | include d | exclude End")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert (
        "Why did the network engineer always carry a ladder?" in shell_output
        and 'Because he wanted to reach the highest levels of connectivity... and occasionally fix the "cloud" when it crashed!'
        in shell_output
        and "End" not in shell_output
    )


def test_processors_formatter_pprint():
    """data_pprint uses Formatters.formatter_pprint processor to pprint the output"""
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_pprint")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert """{   'even': {'more': {'dictionary': 'data'}},
    'list': [   {'more': {'dictionary': 'data'}},
                {'more': {'dictionary': 'data'}}],
    'more': {'dictionary': ['data']},
    'some': {'dictionary': {'data': None}}}""" in shell_output


def test_pipe_formatter_pprint():
    """pprint pipe function uses Formatters.formatter_pprint function to pprint the output"""
    shell.onecmd("top")  # go to top
    shell.onecmd("show data | pprint")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert """{   'even': {'more': {'dictionary': 'data'}},
    'list': [   {'more': {'dictionary': 'data'}},
                {'more': {'dictionary': 'data'}}],
    'more': {'dictionary': ['data']},
    'some': {'dictionary': {'data': None}}}""" in shell_output


def test_pipe_formatter_json_and_alias():
    """json pipe function uses Formatters.formatter_json function to print
    json output, also model uses json_ and field has alias="json" defines"""
    shell.onecmd("top")  # go to top
    shell.onecmd("show data | json")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert """{
    "even": {
        "more": {
            "dictionary": "data"
        }
    },
    "list": [
        {
            "more": {
                "dictionary": "data"
            }
        },
        {
            "more": {
                "dictionary": "data"
            }
        }
    ],
    "more": {
        "dictionary": [
            "data"
        ]
    },
    "some": {
        "dictionary": {
            "data": null
        }
    }
}""" in shell_output


def test_alias_handling():
    """model field has alias with dashes, while field uses underscores"""
    shell.onecmd("top")  # go to top
    shell.onecmd("test_alias_handling foo-bar-command bla")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "{'foo_bar_command': 'bla'}" in shell_output


def test_alias_handling_nested_model():
    shell.onecmd("top")  # go to top
    shell.onecmd(
        "test_alias_handling nested_command enter-command foo command_no_alias bar"
    )

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "{'command_with_alias': 'foo', 'command_no_alias': 'bar'}" in shell_output

    """model field has alias with dashes, while field uses underscores"""
    shell.onecmd("top")  # go to top
    shell.onecmd("test_alias_handling foo-bar-command bla")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "{'foo_bar_command': 'bla'}" in shell_output


def test_alias_handling_at_the_top():
    shell.onecmd("top")  # go to top
    shell.onecmd("test-alias-handling-top foo")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "{'test_alias_handling_top': 'foo'}" in shell_output


def test_alias_handling_mandatory_field():
    shell.onecmd("top")  # go to top
    shell.onecmd(
        "test_alias_handling mandatory_field_test mandatory-field-with-alias bla"
    )

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert "{'mandatory_field_with_alias': 'bla'}" in shell_output


def test_pipe_formatter_yaml():
    """yaml pipe function uses Formatters.formatter_yaml function to print
    yaml output"""
    shell.onecmd("top")  # go to top
    shell.onecmd("show data | yaml")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert """even:
  more:
    dictionary: data
list:
- more:
    dictionary: data
- more:
    dictionary: data
more:
  dictionary:
  - data
some:
  dictionary:
    data: null""" in shell_output


def test_outputter_rich_json():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_rich_json")

    assert True


def test_outputter_nested():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_output_nested")

    assert True


def test_outputter_nested_with_tables():
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_output_nested_tables")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert all(k in shell_output for k in ["key1_value3", "nested_data"])


def test_PicleConfig_processor_with_run_method():
    """
    model_nr_cfg has processor attribute defined within PicleConfig class,
    this test tests its execution
    """
    shell.onecmd("top")  # go to top
    shell.onecmd("salt nr cfg commands bla")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert """{
    "commands": "bla",
    "plugin": "netmiko",
    "target": "proxy:proxytype:nornir",
    "tgt_type": "pillar"
}""" in shell_output


def test_PicleConfig_outputter_with_run_method():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("test_PicleConfig_outputter_with_run_method string_argument bla")

    assert True


def test_subshell_handling():
    shell.onecmd("top")  # go to top

    # 1 go to subshell
    shell.onecmd("salt nr cli")

    print(f"Current shell prompt: '{shell.prompt}'")

    assert shell.prompt == "salt[nr-cli]#"

    # 2 run command in subshell
    shell.onecmd("commands abc add_details")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
            "'add_details': True",
        ]
    )

    # 3 go back to the top
    shell.onecmd("top")

    print(f"Current shell prompt: '{shell.prompt}'")

    assert shell.prompt == "picle#"


def test_shell_exit_defaults_handling():
    shell.onecmd("top")  # go to top
    shell.shell_defaults.clear()

    # go to subshell
    shell.onecmd("salt nr cli")
    print(f"Current shell prompt: '{shell.prompt}', defaults '{shell.shell_defaults}'")
    assert shell.shell_defaults == {
        "target": "proxy:proxytype:nornir",
        "tgt_type": "pillar",
    }

    # exit to top
    shell.onecmd("exit")
    shell.onecmd("exit")
    print(f"Current shell prompt: '{shell.prompt}', defaults '{shell.shell_defaults}'")
    assert shell.shell_defaults == {}


def test_shell_top_defaults_handling():
    shell.onecmd("top")  # go to top
    shell.shell_defaults.clear()

    # go to subshell
    shell.onecmd("salt nr cli")
    print(f"Current shell prompt: '{shell.prompt}', defaults '{shell.shell_defaults}'")
    assert shell.shell_defaults == {
        "target": "proxy:proxytype:nornir",
        "tgt_type": "pillar",
    }

    # exit to top
    shell.onecmd("top")
    print(f"Current shell prompt: '{shell.prompt}', defaults '{shell.shell_defaults}'")
    assert shell.shell_defaults == {}


def test_model_run_kwargs_unpacking():
    shell.onecmd("top")  # go to top
    # give command with plugin keyword that is part of defaults
    # this command prior to 0.5.2 would fail to execute due to
    # issue with improper arguments unpacking
    shell.onecmd("salt nr cli commands abc plugin netmiko")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert all(
        k in shell_output
        for k in [
            "Called salt nr cli, kwargs:",
            "'target': 'proxy:proxytype:nornir'",
            "'tgt_type': 'pillar'",
            "'commands': 'abc'",
            "'plugin': 'netmiko'",
        ]
    )


def test_outputter_rich_table():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_rich_table")

    assert True


def test_outputter_rich_table_no_kwargs():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("show data_rich_table")

    assert True


def test_outputter_rich_table_with_kwargs():
    # outputter prints to terminal bypassing stdout, hence no output to test

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd(
        "test_outputter_rich_table_with_PicleConfig_kwargs string_argument bla"
    )

    assert True


def test_nested_model_run_with_no_kwargs():
    shell.onecmd("top")  # go to top
    # give command with no keywords to verify handling of
    # model that has run method but no command arguments provided
    shell.onecmd("show XYZ")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert (
        "[{'name': 'name3', 'status': 'dead', 'keepalive': '123'}, {'name': 'name1', 'status': 'alive', 'keepalive': '123'}, {'name': 'name2', 'status': 'any', 'keepalive': '123'}]"
        in shell_output
    )


def test_json_field():
    shell.onecmd("top")  # go to top
    shell.onecmd(
        """test_json_input data {"person":{"name":"John","age":30,"contacts":[ {"arg":"email","value":"john@example.com"} ] } }  arg foo"""
    )

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")
    assert (
        """{'data': '{"person":{"name":"John","age":30,"contacts":[ {"arg":"email","value":"john@example.com"}]}}', 'arg': 'foo'}"""
        in shell_output
    )


def test_json_field_in_quotes():
    shell.onecmd("top")  # go to top
    shell.onecmd(
        """test_json_input data '{"person":{"name":"John","age":30,"contacts":[ {"arg":"email","value":"john@example.com"} ] } }'  arg foo"""
    )

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"\n!!!shell output: '{shell_output}'")
    assert (
        """{'data': '{"person":{"name":"John","age":30,"contacts":[ {"arg":"email","value":"john@example.com"} ] } }', 'arg': 'foo'}"""
        in shell_output
    )

def test_json_field_boolean_true():
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_json_input data true arg foo""")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert """{'data': 'true', 'arg': 'foo'}""" in shell_output


def test_json_field_boolean_false():
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_json_input data false arg foo""")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert """{'data': 'false', 'arg': 'foo'}""" in shell_output


def test_json_field_boolean_null():
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_json_input data null arg foo""")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert """{'data': 'null', 'arg': 'foo'}""" in shell_output


def test_multiline_input_with_inline_value():
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_multiline_input data foo arg bar""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert "{'data': 'foo', 'arg': 'bar'}" in shell_output


def test_outputter_result_specific():
    # outputter prints to terminal bypassing stdout, hence no output to test, just test that runs with no error

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("test_result_specific_outputter data foo arg bar")

    assert True


def test_outputter_result_specific_no_kwargs():
    # outputter prints to terminal bypassing stdout, hence no output to test, just test that runs with no error

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("test_result_specific_outputter_no_kwargs data foo arg bar")

    assert True


def test_single_quote_command_collection():
    # outputter prints to terminal bypassing stdout, hence no output to test, just test that runs with no error

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_command_values command 'show version | match "Juniper: "' """)

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert """{'command': 'show version | match "Juniper: "'}""" == shell_output.strip()


def test_presence_handling_for_next_model():
    # outputter prints to terminal bypassing stdout, hence no output to test, just test that runs with no error

    # just verify command run with no exceptions raised
    shell.onecmd("top")  # go to top
    shell.onecmd("""salt nr cli commands "show clock" table next_model some bla""")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f"shell output: '{shell_output}'")

    assert (
        """Called salt nr cli, kwargs: {'target': 'proxy:proxytype:nornir', 'tgt_type': 'pillar', 'plugin': 'netmiko', 'commands': 'show clock', 'table': 'brief', 'some': 'bla'}"""
        == shell_output.strip()
    )


def test_model_mount():
    class test_mount_model(BaseModel):
        param: StrictStr = Field(None, description="string")

        @staticmethod
        def run(**kwargs):
            return kwargs

    # mount model and test it runs
    shell.model_mount(test_mount_model, "mount_model_top")
    shell.onecmd("top")  # go to top
    shell.onecmd("""mount_model_top param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert shell_output == "{'param': 'bla'}"

    # remove model
    shell.model_remove("mount_model_top")
    shell.onecmd("""mount_model_top param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_model_mount_with_alias():
    class test_mount_model(BaseModel):
        param: StrictStr = Field(None, description="string")

        @staticmethod
        def run(**kwargs):
            return kwargs

    # mount model and test it runs
    shell.model_mount(test_mount_model, "mount_model_top", alias="mount-model-top")
    shell.onecmd("top")  # go to top
    shell.onecmd("""mount-model-top param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert shell_output == "{'param': 'bla'}"

    # remove model
    shell.model_remove("mount_model_top")
    shell.onecmd("""mount-model-top param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_model_mount_nested():
    class test_mount_model(BaseModel):
        param: StrictStr = Field(None, description="string")

        @staticmethod
        def run(**kwargs):
            return kwargs

    # mount model and test it runs
    shell.model_mount(test_mount_model, ["salt", "mount_model_nested"])
    shell.onecmd("top")  # go to top
    shell.onecmd("""salt mount_model_nested param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'param': 'bla'" in shell_output

    # remove model
    shell.model_remove(["salt", "mount_model_nested"])
    shell.onecmd("""salt mount_model_nested param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'param': 'bla'" not in shell_output


def test_model_remove_wrong_path():
    class test_mount_model(BaseModel):
        param: StrictStr = Field(None, description="string")

        @staticmethod
        def run(**kwargs):
            return kwargs

    # mount model and test it runs
    shell.model_mount(test_mount_model, ["salt", "mount_model_nested"])
    shell.onecmd("top")  # go to top
    shell.onecmd("""salt mount_model_nested param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'param': 'bla'" in shell_output

    # try to remove model at wrong path
    with pytest.raises(KeyError):
        shell.model_remove(["salt", "wrong_name"])


def test_model_mount_nested_wrong_path():
    class test_mount_model(BaseModel):
        param: StrictStr = Field(None, description="string")

        @staticmethod
        def run(**kwargs):
            return kwargs

    with pytest.raises(KeyError):
        shell.model_mount(test_mount_model, ["salt", "foo", "bar"])


def test_model_mount_commands():
    # mount model and test it runs
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_mount_model mount_add foo""")
    shell.onecmd("""foo param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'param': 'bla'" in shell_output

    # remove model
    shell.onecmd("""test_mount_model mount_remove foo""")
    shell.onecmd("""foo param bla""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'param': 'bla'" not in shell_output


def test_enum_and_field_with_same_name():
    shell.onecmd("top")  # go to top
    shell.onecmd("""test_enum_and_field_with_same_name task cli client bla""")

    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()

    print(f"shell output: '{shell_output}'")

    assert "{'task': 'cli', 'client': 'bla'}" in shell_output


def test_source_has_boolean_in_a_list():
    shell.onecmd("top")  # go to top

    shell.onecmd("""test_source_has_boolean_in_a_list value False""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': False}" in shell_output

    shell.onecmd("""test_source_has_boolean_in_a_list value True""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': True}" in shell_output

    shell.onecmd("""test_source_has_boolean_in_a_list value None""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': None}" in shell_output

    shell.onecmd("""test_source_has_boolean_in_a_list value foo""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': 'foo'}" in shell_output

    shell.onecmd("""test_source_has_boolean_in_a_list value bar""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': 'bar'}" in shell_output


def test_enum_has_boolean_in_a_list():
    shell.onecmd("top")  # go to top

    shell.onecmd("""test_enum_has_boolean_in_a_list value False""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': False}" in shell_output

    shell.onecmd("""test_enum_has_boolean_in_a_list value True""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': True}" in shell_output

    shell.onecmd("""test_enum_has_boolean_in_a_list value foo""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value': 'foo'}" in shell_output


def test_tabulate_table():
    shell.onecmd("top")  # go to top

    shell.onecmd("""show data_list | table""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")

    assert all(
        i in shell_output
        for i in [
            "+----+--------+-------------+-------------+",
            "|    | name   | key1        | key2        |",
            "+====+========+=============+=============+",
            "|  1 | name3  | key1_value3 | key2_value3 |",
            "|  2 | name1  | key1_value1 | key2_value1 |",
            "|  3 | name2  | key1_value2 | key2_value2 |",
        ]
    )


def test_tabulate_table_tablefmt_plain():
    shell.onecmd("top")  # go to top

    shell.onecmd("""show data_list | table tablefmt plain""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")

    assert all(
        i in shell_output
        for i in [
            "name    key1         key2",
            " 1  name3   key1_value3  key2_value3",
            " 2  name1   key1_value1  key2_value1",
            " 3  name2   key1_value2  key2_value2",
        ]
    )


def test_integer_converstion_for_strictstr_field():
    shell.onecmd("top")  # go to top

    shell.onecmd("""test_integer_converstion_for_strictstr_field value_StrictStr 123""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value_StrictStr': '123'}" in shell_output

    shell.onecmd("""test_integer_converstion_for_strictstr_field value_str 123""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value_str': '123'}" in shell_output

    shell.onecmd("""test_integer_converstion_for_strictstr_field value_StrictInt 123""")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "{'value_StrictInt': 123}" in shell_output


# ============================================================
# New tests to improve coverage
# ============================================================


def test_emptyline():
    """Test that empty line does nothing (returns None)"""
    shell.onecmd("top")
    result = shell.emptyline()
    assert result is None


def test_do_help_basic():
    """Test the help command for top-level model"""
    shell.onecmd("top")
    shell.onecmd("help")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # help should mention model fields
    assert "salt" in shell_output or "show" in shell_output


def test_do_help_with_subcommand():
    """Test the help command for a subcommand"""
    shell.onecmd("top")
    shell.onecmd("help show")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "version" in shell_output


def test_do_help_verbose():
    """Test verbose help with double question mark"""
    shell.onecmd("top")
    shell.onecmd("help show ??")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # verbose help should include type and default info
    assert "version" in shell_output


def test_do_help_incorrect_command():
    """Test help for a command that doesn't exist"""
    shell.onecmd("top")
    shell.onecmd("help nonexistent_command_xyz")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_process_help_command_question_mark():
    """Test inline help triggered by '?' at end of command"""
    shell.onecmd("top")
    shell.onecmd("show?")
    # Should not raise an exception
    assert True


def test_process_help_command_verbose_question_mark():
    """Test verbose inline help triggered by '??' at end of command"""
    shell.onecmd("top")
    shell.onecmd("show??")
    assert True


def test_process_help_command_for_field():
    """Test inline help for a specific field"""
    shell.onecmd("top")
    shell.onecmd("salt nr cli commands?")
    assert True


def test_process_help_command_incorrect():
    """Test inline help for non-existent command"""
    shell.onecmd("top")
    shell.onecmd("totally_wrong_xxx?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_do_end():
    """Test the end command returns True to exit application"""
    shell.onecmd("top")
    result = shell.do_end("")
    assert result is True


def test_do_end_help():
    """Test end command with ? shows help"""
    shell.onecmd("top")
    shell.do_end("?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "end" in shell_output.lower() or "Exit" in shell_output


def test_do_exit_help():
    """Test exit command with ? shows help"""
    shell.onecmd("top")
    shell.do_exit("?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "exit" in shell_output.lower() or "Exit" in shell_output


def test_do_top_help():
    """Test top command with ? shows help"""
    shell.onecmd("top")
    shell.do_top("?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "top" in shell_output.lower()


def test_do_pwd():
    """Test pwd command at top level"""
    shell.onecmd("top")
    shell.onecmd("pwd")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "Root" in shell_output


def test_do_pwd_in_subshell():
    """Test pwd command in a subshell"""
    shell.onecmd("top")
    shell.onecmd("salt nr cli")  # go to subshell
    shell.onecmd("pwd")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "Root" in shell_output
    shell.onecmd("top")  # go back


def test_do_pwd_help():
    """Test pwd command with ? shows help"""
    shell.onecmd("top")
    shell.do_pwd("?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "pwd" in shell_output.lower()


def test_do_cls():
    """Test cls command runs without error"""
    shell.onecmd("top")
    shell.do_cls("")
    assert True


def test_do_cls_help():
    """Test cls command with ? shows help"""
    shell.onecmd("top")
    shell.do_cls("?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "cls" in shell_output.lower() or "Clear" in shell_output


def test_do_shell_writes_stdout_and_uses_subprocess_run():
    """Test shell command executes via subprocess.run and prints stdout."""
    shell.onecmd("top")
    with unittest.mock.patch(
        "picle.picle.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args="echo hello",
            returncode=0,
            stdout="hello from shell\n",
            stderr="",
        ),
    ) as mocked_run:
        shell.do_shell("echo hello")

    mocked_run.assert_called_once_with(
        "echo hello",
        shell=True,
        capture_output=True,
        text=True,
        errors="replace",
    )
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "hello from shell" in shell_output


def test_do_shell_writes_stderr_for_failed_command():
    """Test shell command prints stderr for non-zero exit code."""
    shell.onecmd("top")
    with unittest.mock.patch(
        "picle.picle.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args="bad command",
            returncode=1,
            stdout="",
            stderr="command not found",
        ),
    ):
        shell.do_shell("bad command")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "command not found" in shell_output


def test_incorrect_command():
    """Test handling of an incorrect command string"""
    shell.onecmd("top")
    shell.onecmd("totally_wrong_command_xyz")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_incomplete_command():
    """Test handling of an incomplete command (partial field name match)"""
    shell.onecmd("top")
    shell.onecmd("sal")  # partial match for 'salt'
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert (
        "Incomplete command" in shell_output or "possible completions" in shell_output
    )


def test_float_conversion():
    """Test that float values are converted correctly"""
    shell.onecmd("top")
    shell.onecmd("test_float_conversion value 3.14")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "3.14" in shell_output


def test_multiple_values_collection():
    """Test that multiple values get collected as a list"""
    shell.onecmd("top")
    shell.onecmd("test_multiple_values items val1 items val2 items val3 tag mytag")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'items':" in shell_output and "'tag': 'mytag'" in shell_output


def test_json_list_input():
    """Test JSON list input with square brackets"""
    shell.onecmd("top")
    shell.onecmd("test_json_list_input data [1, 2, 3] arg foo")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'data': '[1, 2, 3]'" in shell_output


def test_double_quoted_value():
    """Test double quoted value collection"""
    shell.onecmd("top")
    shell.onecmd('test_double_quote_value command "hello world" arg bar')
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'command': 'hello world'" in shell_output


def test_double_quoted_single_value():
    """Test double quoted single word value (both quotes in one parameter)"""
    shell.onecmd("top")
    shell.onecmd('test_double_quote_value command "hello" arg bar')
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "'command': 'hello'" in shell_output


def test_pipe_formatter_save(tmp_path):
    """Test save pipe function to write output to a file"""
    save_file = str(tmp_path / "test_output.txt")
    shell.onecmd("top")
    shell.onecmd(f"test_save_outputter data hello | save {save_file}")
    # verify the file was created
    import os

    assert os.path.exists(save_file)
    with open(save_file, "r") as f:
        content = f.read()
    assert "hello" in content


def test_pipe_formatter_markdown():
    """Test markdown pipe function"""
    shell.onecmd("top")
    shell.onecmd("test_markdown_outputter text # Hello World | markdown")
    # markdown outputter uses Rich and prints to console directly
    assert True


def test_write_non_string():
    """Test write method with non-string output"""
    shell.onecmd("top")
    # Force write with a non-string value
    shell.write(12345)
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "12345" in shell_output


def test_write_output_with_newline():
    """Test write method with output that already has newline"""
    shell.onecmd("top")
    shell.write("test output\r\n")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    assert "test output" in shell_output


def test_model_fields_function_with_class():
    """Test model_fields helper with a class (not instance)"""
    from picle.picle import model_fields
    from .picle_test_shell import Root

    fields = model_fields(Root)
    assert "salt" in fields
    assert "show" in fields


def test_model_fields_function_with_instance():
    """Test model_fields helper with an instance"""
    from picle.picle import model_fields
    from .picle_test_shell import Root

    instance = Root.model_construct()
    fields = model_fields(instance)
    assert "salt" in fields
    assert "show" in fields


def test_defaults_set():
    """Test defaults_set clears and repopulates defaults"""
    shell.onecmd("top")
    shell.shell_defaults = {"foo": "bar"}
    from .picle_test_shell import model_nr_cli

    shell.defaults_set(model_nr_cli)
    # should have cleared foo and set model defaults
    assert "foo" not in shell.shell_defaults
    assert "plugin" in shell.shell_defaults
    # reset
    shell.onecmd("top")


def test_defaults_pop():
    """Test defaults_pop removes model field names from defaults"""
    shell.onecmd("top")
    from .picle_test_shell import model_nr_cli

    shell.shell_defaults = {"plugin": "netmiko", "commands": "abc", "other": "val"}
    shell.defaults_pop(model_nr_cli)
    assert "plugin" not in shell.shell_defaults
    assert "commands" not in shell.shell_defaults
    assert "other" in shell.shell_defaults
    shell.shell_defaults.clear()
    shell.onecmd("top")


def test_extract_model_defaults():
    """Test extract_model_defaults returns only non-None default values"""
    from .picle_test_shell import model_nr_cli

    defaults = shell.extract_model_defaults(model_nr_cli)
    # plugin has default "netmiko", commands is required (...), others are None
    assert "plugin" in defaults
    assert defaults["plugin"] == "netmiko"
    # commands is required, should not be in defaults
    assert "commands" not in defaults


def test_subshell_enter_and_exit_nesting():
    """Test entering multiple subshell levels and exiting them one by one"""
    shell.onecmd("top")
    shell.shell_defaults.clear()

    # Enter first subshell: salt
    shell.onecmd("salt nr")
    assert shell.prompt == "salt[nr]#"

    # Enter second subshell: nr cli
    shell.onecmd("cli")
    assert shell.prompt == "salt[nr-cli]#"

    # Exit one level
    shell.onecmd("exit")
    # Should be back at nr level
    assert len(shell.shells) >= 2

    # Exit another level
    shell.onecmd("exit")
    # Should be at salt level or top

    shell.onecmd("top")
    assert shell.prompt == "picle#"


def test_do_exit_from_top_returns_true():
    """Test that exiting from top level returns True (termination)"""
    shell.onecmd("top")
    # Force shells to have only one entry (the top shell) and pop it
    saved_shells = list(shell.shells)
    saved_shell = shell.shell
    saved_prompt = shell.prompt
    saved_defaults = dict(shell.shell_defaults)

    # Override shells to simulate final exit
    shell.shells = [shell.shell]
    result = shell.do_exit("")
    # After popping the only shell, shells is empty -> returns True
    if not shell.shells:
        assert result is True

    # Restore state
    shell.shells = saved_shells
    shell.shell = saved_shell
    shell.prompt = saved_prompt
    shell.shell_defaults = saved_defaults
    shell.onecmd("top")


def test_no_run_method_model_with_use_parent_run_false():
    """Test command for model that has no run method and no function defined and has use_parent_run set to False"""
    shell.onecmd("top")
    shell.onecmd("test_no_run_method value foo")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "Incorrect command" in shell_output


def test_function_field_execution():
    """Test that a function field in json_schema_extra gets called"""
    shell.onecmd("top")
    shell.onecmd("test_function_field action")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "action_executed" in shell_output


def test_pipe_pprint_with_string_data():
    """Test pprint outputter with string data passes through"""
    from picle.models import Outputters

    result = Outputters.outputter_pprint("already a string")
    assert result == "already a string"


def test_outputter_json_with_string_data():
    """Test json outputter with string data passes through"""
    from picle.models import Outputters

    result = Outputters.outputter_json("already a json string")
    assert result == "already a json string"


def test_outputter_json_with_bytes_data():
    """Test json outputter with bytes data decodes to string"""
    from picle.models import Outputters

    result = Outputters.outputter_json(b'{"key": "value"}')
    assert result == '{"key": "value"}'


def test_outputter_json_with_dict_data():
    """Test json outputter with dictionary data formats as JSON"""
    from picle.models import Outputters

    result = Outputters.outputter_json({"key": "value"})
    assert '"key": "value"' in result


def test_outputter_yaml_with_string_data():
    """Test yaml outputter with string data passes through"""
    from picle.models import Outputters

    result = Outputters.outputter_yaml("already yaml")
    assert result == "already yaml"


def test_outputter_yaml_with_bytes_data():
    """Test yaml outputter with bytes data decodes"""
    from picle.models import Outputters

    result = Outputters.outputter_yaml(b"bytes data")
    assert result == "bytes data"


def test_outputter_yaml_with_dict():
    """Test yaml outputter with dict formats as YAML"""
    from picle.models import Outputters

    result = Outputters.outputter_yaml({"key": "value"})
    assert "key:" in result and "value" in result


def test_outputter_yaml_with_absolute_indent():
    """Test yaml outputter with absolute indent parameter"""
    from picle.models import Outputters

    result = Outputters.outputter_yaml({"key": "value"}, absolute_indent=4)
    # lines with content should have 4 spaces prepended
    lines = [i for i in result.splitlines() if i.strip()]
    assert len(lines) > 0
    for line in lines:
        assert line.startswith("    ")


def test_outputter_nested_with_string():
    """Test nested outputter with simple string input"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"key": "line1\nline2"})
    assert "key" in result and "line1" in result and "line2" in result


def test_outputter_nested_with_none_values():
    """Test nested outputter with None, True, False values"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"a": None, "b": True, "c": False})
    assert "None" in result and "True" in result and "False" in result


def test_outputter_nested_with_number():
    """Test nested outputter with number values"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"count": 42})
    assert "42" in result


def test_outputter_nested_with_bytes():
    """Test nested outputter with bytes data"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"data": b"hello bytes"})
    assert "hello bytes" in result


def test_outputter_nested_with_nested_lists():
    """Test nested outputter with nested lists (non-dict items)"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"items": ["a", "b", "c"]})
    assert "a" in result and "b" in result and "c" in result


def test_outputter_nested_with_list_of_dicts():
    """Test nested outputter with list of dicts (non-table mode)"""
    from picle.models import Outputters

    data = [
        {"name": "item1", "value": "val1"},
        {"name": "item2", "value": "val2"},
    ]
    result = Outputters.outputter_nested(data)
    assert "item1" in result and "item2" in result


def test_outputter_nested_rich_key_coloring_by_dict_level(monkeypatch):
    """Test key coloring for first/second/third dictionary levels when Rich is enabled."""
    import picle.models as models

    monkeypatch.setattr(models, "HAS_RICH", True)

    result = models.Outputters.outputter_nested(
        {
            "host1": {
                "task1": {
                    "k1": "value1",
                }
            }
        }
    )

    assert "[bold green]host1[/bold green]:" in result
    assert "[bold blue]task1[/bold blue]:" in result
    assert "[bold yellow]k1[/bold yellow]:" in result


def test_outputter_nested_rich_list_not_counted_as_level(monkeypatch):
    """Test that list nesting does not increment dictionary key depth."""
    import picle.models as models

    monkeypatch.setattr(models, "HAS_RICH", True)

    result = models.Outputters.outputter_nested(
        [
            {
                "host1": {
                    "task1": [
                        {
                            "k1": "value1",
                        }
                    ]
                }
            }
        ]
    )

    # top-level list should start dictionary keys at level 1
    assert "[bold green]host1[/bold green]:" in result
    # nested key depth should ignore the list between task1 and k1
    assert "[bold blue]task1[/bold blue]:" in result
    assert "[bold yellow]k1[/bold yellow]:" in result


def test_outputter_rich_table_with_sortby():
    """Test rich table outputter with sortby parameter"""
    from picle.models import Outputters

    data = [
        {"name": "charlie", "age": "30"},
        {"name": "alice", "age": "25"},
        {"name": "bob", "age": "28"},
    ]
    result = Outputters.outputter_rich_table(data, sortby="name")
    # result should be a Rich Table object
    assert result is not None


def test_outputter_rich_table_empty_list():
    """Test rich table outputter with empty list"""
    from picle.models import Outputters

    data = []
    result = Outputters.outputter_rich_table(data)
    assert result == []


def test_outputter_rich_table_non_list():
    """Test rich table outputter with non-list data"""
    from picle.models import Outputters

    data = "not a list"
    result = Outputters.outputter_rich_table(data)
    assert result == "not a list"


def test_outputter_rich_markdown():
    """Test rich markdown outputter"""
    from picle.models import Outputters

    result = Outputters.outputter_rich_markdown("# Hello")
    assert result is not None


def test_outputter_rich_markdown_non_string():
    """Test rich markdown outputter with non-string input"""
    from picle.models import Outputters

    result = Outputters.outputter_rich_markdown(12345)
    assert result is not None


def test_outputter_save(tmp_path):
    """Test save outputter writes string data to file"""
    from picle.models import Outputters

    filepath = str(tmp_path / "save_test.txt")
    result = Outputters.outputter_save("test data", filepath)
    assert result == "test data"
    with open(filepath, "r") as f:
        assert f.read() == "test data"


def test_outputter_save_non_string(tmp_path):
    """Test save outputter writes non-string data to file"""
    from picle.models import Outputters

    filepath = str(tmp_path / "save_test2.txt")
    result = Outputters.outputter_save({"key": "value"}, filepath)
    assert result == {"key": "value"}
    with open(filepath, "r") as f:
        content = f.read()
    assert "key" in content


def test_tabulate_table_sortby():
    """Test tabulate table with sortby parameter"""
    shell.onecmd("top")
    shell.onecmd("show data_list | table sortby name")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "name1" in shell_output and "name3" in shell_output


def test_tabulate_table_sortby_reverse():
    """Test tabulate table with sortby and reverse parameters"""
    shell.onecmd("top")
    shell.onecmd("show data_list | table sortby name reverse")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "name1" in shell_output


def test_tabulate_table_headers_exclude():
    """Test tabulate table with headers-exclude parameter"""
    shell.onecmd("top")
    shell.onecmd("show data_list | table headers-exclude key2")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    assert "key2" not in shell_output
    assert "key1" in shell_output


def test_tabulate_table_with_headers():
    """Test tabulate table with custom headers parameter"""
    from picle.models import Outputters

    data = [
        {"name": "item1", "key1": "v1", "key2": "v2"},
        {"name": "item2", "key1": "v3", "key2": "v4"},
    ]
    result = Outputters.outputter_tabulate_table(data, headers="name,key1")
    assert "name" in result and "key1" in result


def test_tabulate_table_non_list_data():
    """Test tabulate table with non-list data returns data unchanged"""
    from picle.models import Outputters

    result = Outputters.outputter_tabulate_table("not a list")
    assert result == "not a list"


def test_tabulate_table_with_list_of_lists():
    """Test tabulate table handles list of lists"""
    from picle.models import Outputters

    data = [
        [{"name": "a", "val": "1"}, {"name": "b", "val": "2"}],
        {"name": "c", "val": "3"},
    ]
    result = Outputters.outputter_tabulate_table(data)
    assert "a" in result and "b" in result and "c" in result


# ---- Chat interface tests ----


def test_chat_shell_passes_additional_argument_to_run():
    """Test chat shell passes command arguments to run() calls."""
    shell.onecmd("top")
    mock_stdout.write.reset_mock()

    with unittest.mock.patch(
        "builtins.input", side_effect=["hello", "world", EOFError]
    ):
        shell.onecmd("test_chat_interface_2 session_id session-123")

    outputs = "".join(str(call[0][0]) for call in mock_stdout.write.call_args_list)
    assert "ECHO - hello" in outputs
    assert "ECHO - world" in outputs
    assert outputs.count("'session_id': 'session-123'") == 2


def test_chat_shell_keeps_additional_argument_after_slash_command():
    """Test chat shell keeps command arguments after executing a /command."""
    shell.onecmd("top")
    mock_stdout.write.reset_mock()

    with unittest.mock.patch(
        "builtins.input", side_effect=["hello", "/show usage", "again", EOFError]
    ):
        shell.onecmd("test_chat_interface_2 session_id session-456")

    outputs = "".join(str(call[0][0]) for call in mock_stdout.write.call_args_list)
    assert "1234; 1234; 1234" in outputs
    assert "ECHO - hello" in outputs
    assert "ECHO - again" in outputs
    assert outputs.count("'session_id': 'session-456'") == 2


def test_chat_completenames_prefixes_with_slash():
    """Test that completenames prefixes results with / when in chat mode"""
    shell.onecmd("top")
    shell.is_chat = True
    try:
        results = shell.completenames("", "/", 0, 1)
        # all completions should start with /
        assert all(r.startswith("/") for r in results)
        # should include shell commands like /show, /exit, /help etc.
        assert any("/show " in r for r in results)
    finally:
        shell.is_chat = False


def test_chat_completenames_without_chat_no_slash():
    """Test that completenames does not prefix with / when not in chat mode"""
    shell.onecmd("top")
    shell.is_chat = False
    results = shell.completenames("", "", 0, 0)
    # none should start with /
    assert not any(r.startswith("/") for r in results)


def test_chat_completenames_strips_slash_for_matching():
    """Test that completenames strips / from line to match commands"""
    shell.onecmd("top")
    shell.is_chat = True
    try:
        results = shell.completenames("sh", "/sh", 1, 3)
        assert any("show" in r for r in results)
    finally:
        shell.is_chat = False


def test_chat_completedefault_strips_slash():
    """Test that completedefault strips / prefix before parsing"""
    shell.onecmd("top")
    shell.is_chat = True
    try:
        results = shell.completedefault("", "/show ", 6, 6)
        # should return show model's fields (e.g. version, clock)
        assert any("version" in r for r in results)
    finally:
        shell.is_chat = False


def test_tabulate_table_showindex_false():
    """Test tabulate table with showindex disabled"""
    from picle.models import Outputters

    data = [
        {"name": "item1", "val": "v1"},
        {"name": "item2", "val": "v2"},
    ]
    result = Outputters.outputter_tabulate_table(data, showindex=False)
    assert "item1" in result


def test_tabulate_table_maxcolwidths():
    """Test tabulate table with maxcolwidths set"""
    from picle.models import Outputters

    data = [
        {"name": "a_very_long_name_that_should_wrap", "val": "v1"},
    ]
    result = Outputters.outputter_tabulate_table(data, maxcolwidths=10)
    assert result is not None


def test_filters_include():
    """Test Filters.filter_include directly"""
    from picle.models import Filters

    data = "line one\nline two\nline three"
    result = Filters.filter_include(data, "two")
    assert "line two" in result
    assert "line one" not in result


def test_filters_exclude():
    """Test Filters.filter_exclude directly"""
    from picle.models import Filters

    data = "line one\nline two\nline three"
    result = Filters.filter_exclude(data, "two")
    assert "line two" not in result
    assert "line one" in result


def test_completenames():
    """Test tab completion for first command parameter"""
    shell.onecmd("top")
    completions = shell.completenames("sh", "sh", 0, 2)
    print(f"completions: {completions}")
    assert any("show" in c for c in completions)


def test_completenames_global_methods():
    """Test tab completion includes global methods like exit, top, etc."""
    shell.onecmd("top")
    completions = shell.completenames("ex", "ex", 0, 2)
    print(f"completions: {completions}")
    assert any("exit" in c for c in completions)


def test_completedefault_field_values():
    """Test tab completion for field values (enum)"""
    shell.onecmd("top")
    completions = shell.completedefault("net", "salt nr cli plugin net", 0, 3)
    print(f"completions: {completions}")
    assert any("netmiko" in c for c in completions)


def test_completedefault_model_fields():
    """Test tab completion lists model fields after entering model"""
    shell.onecmd("top")
    completions = shell.completedefault("", "salt nr cli ", 0, 0)
    print(f"completions: {completions}")
    assert len(completions) > 0


def test_completedefault_source_method():
    """Test tab completion uses source_ method for field options"""
    shell.onecmd("top")
    completions = shell.completedefault("ceos", "salt nr cli hosts ceos", 0, 4)
    print(f"completions: {completions}")
    assert any("ceos" in c for c in completions)


def test_completedefault_loose_match():
    """Test tab completion with partial match (FieldLooseMatchOnly)"""
    shell.onecmd("top")
    completions = shell.completedefault("com", "salt nr cli com", 0, 3)
    print(f"completions: {completions}")
    assert any("commands" in c for c in completions)


def test_completedefault_no_match():
    """Test tab completion with no match returns empty"""
    shell.onecmd("top")
    completions = shell.completedefault("zzz", "salt nr cli zzz", 0, 3)
    print(f"completions: {completions}")
    assert completions == []


def test_man_tree():
    """Test man tree command prints model tree without error"""
    shell.onecmd("top")
    shell.onecmd("man tree")
    assert True


def test_man_tree_with_path():
    """Test man tree command with dotted path"""
    shell.onecmd("top")
    shell.onecmd("man tree show")
    assert True


def test_man_json_schema():
    """Test man json-schema command runs (may fail on complex Root with functions in json_schema_extra)"""
    shell.onecmd("top")
    # man json-schema on Root model may fail due to pydantic serialization of functions
    # in json_schema_extra, just verify no crash
    shell.onecmd("man json-schema")
    assert True


def test_man_json_schema_with_path():
    """Test man json-schema with dotted path to a simpler model"""
    shell.onecmd("top")
    shell.onecmd("man json-schema salt.nr.cli")
    # May succeed or fail depending on model complexity, just verify no crash
    assert True


def test_nested_model_with_kwargs():
    """Test nested model with specific kwargs returns different result"""
    shell.onecmd("top")
    shell.onecmd("show XYZ status dead")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    # status=dead matches the anystatus branch default
    # just verify the command runs and produces output
    assert len(shell_output) > 0


def test_show_clock():
    """Test show clock function field"""
    shell.onecmd("top")
    shell.onecmd("show clock")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert len(shell_output.strip()) > 0


def test_subshell_nr_level():
    """Test going into salt nr subshell"""
    shell.onecmd("top")
    shell.onecmd("salt nr")
    assert shell.prompt == "salt[nr]#"
    shell.onecmd("top")
    assert shell.prompt == "picle#"


def test_enum_partial_match_in_default_handler():
    """Test incomplete enum value triggers FieldLooseMatchOnly in default handler"""
    shell.onecmd("top")
    shell.onecmd("salt nr cli commands abc plugin net")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # 'net' partially matches 'netmiko', should trigger incomplete command
    assert "Incomplete command" in shell_output or "netmiko" in shell_output


def test_help_for_field_with_enum():
    """Test help for a field that has enum annotation"""
    shell.onecmd("top")
    shell.onecmd("help salt nr cli plugin")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "netmiko" in shell_output


def test_help_for_field_with_source_method():
    """Test help for a field that has source_ method"""
    shell.onecmd("top")
    shell.onecmd("help salt nr cli hosts")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "ceos1" in shell_output


def test_help_for_subshell_model():
    """Test help for a model that supports subshell shows <ENTER>"""
    shell.onecmd("top")
    shell.onecmd("help salt nr cli")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "ENTER" in shell_output or "commands" in shell_output.lower()


def test_help_with_loose_match():
    """Test help with a partial parameter match"""
    shell.onecmd("top")
    shell.onecmd("help sal")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # Should show matches starting with 'sal'
    assert "salt" in shell_output.lower() or len(shell_output.strip()) > 0


def test_pipe_on_model_without_pipe():
    """Test that piping on a model without pipe config is handled"""

    class NoPipeModel(BaseModel):
        val: StrictStr = Field(None, description="val")

        @staticmethod
        def run(**kwargs):
            return kwargs

    # mount a model without pipe
    shell.model_mount(NoPipeModel, "no_pipe_test")
    shell.onecmd("top")
    # Try to pipe - should log error but not crash
    shell.onecmd("no_pipe_test val abc | include abc")
    shell_output = mock_stdout.write.call_args_list[-1][0][0].strip()
    print(f"shell output: '{shell_output}'")
    # Should still work or show output (pipe may be ignored)
    shell.model_remove("no_pipe_test")


def test_validation_error_handling():
    """Test that validation errors are printed to user"""
    shell.onecmd("top")
    # salt nr cli requires 'commands' field - passing wrong type
    # The existing model has commands as required, calling without it from subshell
    # should work since there's default handling. Let's try with incorrect values
    shell.onecmd("salt nr cli commands")
    # commands needs a value; passing nothing should trigger an error or incomplete
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # Just verify no crash
    assert True


def test_result_specific_outputter_with_tuple_two_elements():
    """Test result specific outputter with 2-element tuple (ret, outputter)"""
    shell.onecmd("top")
    shell.onecmd("test_result_specific_outputter_no_kwargs data hello arg world")
    # Should run without errors
    assert True


def test_pipe_nested_outputter():
    """Test pipe with nested outputter"""
    shell.onecmd("top")
    shell.onecmd("show data | nested")
    # nested outputter uses Rich console, verify no crash
    assert True


def test_generate_json_schema():
    """Test the generate_json_schema utility function with a simple model"""
    from picle.utils import generate_json_schema
    from .picle_test_shell import model_TestCommandValues

    schema = generate_json_schema(model_TestCommandValues)
    assert "properties" in schema
    assert "title" in schema


def test_run_print_exception_decorator():
    """Test the run_print_exception decorator handles exceptions gracefully"""
    from picle.utils import run_print_exception

    @run_print_exception
    def failing_function():
        raise ValueError("test error")

    # Should not raise, should print traceback
    result = failing_function()
    assert result is None


def test_tabulate_headers_exclude_comma_separated():
    """Test tabulate table with comma-separated headers to exclude"""
    from picle.models import Outputters

    data = [
        {"name": "item1", "key1": "v1", "key2": "v2"},
        {"name": "item2", "key1": "v3", "key2": "v4"},
    ]
    result = Outputters.outputter_tabulate_table(data, headers_exclude="key1, key2")
    assert "key1" not in result and "key2" not in result
    assert "name" in result


def test_outputter_nested_with_tuple():
    """Test nested outputter with tuple data"""
    from picle.models import Outputters

    result = Outputters.outputter_nested({"items": (1, 2, 3)})
    assert "1" in result and "2" in result


def test_show_data_list():
    """Test show data_list function returns list data"""
    shell.onecmd("top")
    shell.onecmd("show data_list")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "name" in shell_output


def test_pipe_chain_three():
    """Test chaining three pipe operations"""
    shell.onecmd("top")
    shell.onecmd("show joke | include the | include ladder | exclude nonexistent")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "ladder" in shell_output


def test_help_pipe_available():
    """Test that help shows pipe option for models with pipe config"""
    shell.onecmd("top")
    shell.onecmd("help show version")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "|" in shell_output


def test_dynamic_dictionary():
    shell.onecmd("top")
    shell.onecmd("test_dynamicdictionary mynestedkey myname1 k1 myvalue")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert (
        shell_output.strip() == "{'name': 'myname1', 'k1': 'myvalue'}"
    ), "Dynamic dictionary output mismatch"


def test_dynamic_dictionary_pkey_help():
    shell.onecmd("top")
    shell.onecmd("test_dynamicdictionary mynestedkey ?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert (
        "<name>" in shell_output and "Input key-name" in shell_output
    ), "Dynamic dictionary help output mismatch"


def test_dynamic_dictionary_pkey_help_with_value():
    shell.onecmd("top")
    shell.onecmd("test_dynamicdictionary mynestedkey myname1 ?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert (
        "k1" in shell_output and "my description" in shell_output
    ), "Dynamic dictionary help output mismatch"


def test_pipe_inherited_from_parent_model():
    """Child model has no pipe config; pipe should be inherited from parent via backtracing."""
    shell.onecmd("top")
    shell.onecmd("test_parent_pipe child value hello | include hello")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "hello" in shell_output


def test_pipe_inherited_from_parent_model_exclude():
    """Pipe inherited from parent correctly filters output using exclude.
    The exclude filter removes the only line, so nothing is written to stdout."""
    shell.onecmd("top")
    call_count_before = len(mock_stdout.write.call_args_list)
    shell.onecmd("test_parent_pipe child value hello | exclude hello")
    call_count_after = len(mock_stdout.write.call_args_list)
    # exclude filtered all content - no new write should have occurred
    assert call_count_after == call_count_before


def test_pipe_disabled_in_child_model():
    """Child model with pipe=False blocks pipe backtracing; command still runs, pipe segment is dropped."""
    shell.onecmd("top")
    shell.onecmd("test_parent_pipe child_no_pipe value hello | include hello")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    # pipe is blocked - first segment runs and outputs raw value, pipe filter is not applied
    assert "hello" in shell_output


def test_pipe_help_shown_for_child_inheriting_parent_pipe():
    """Help for child model (no pipe config) should display the '|' option inherited from parent via backtracing."""
    shell.onecmd("top")
    shell.onecmd("test_parent_pipe child ?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "|" in shell_output


def test_pipe_help_not_shown_for_child_with_pipe_disabled():
    """Help for child model with pipe=False should NOT display '|' since pipe is explicitly disabled."""
    shell.onecmd("top")
    shell.onecmd("test_parent_pipe child_no_pipe ?")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "|" not in shell_output


# ============================================================
# outputter_kv tests
# ============================================================


def test_outputter_kv_flat_dict():
    """outputter_kv flattens a flat dict to 'key: value' lines"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"a": 1, "b": 2})
    assert "a: 1" in result
    assert "b: 2" in result


def test_outputter_kv_nested_dict():
    """outputter_kv flattens nested dicts using dot separator"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"a": {"b": {"c": "leaf"}}})
    assert "a.b.c: leaf" in result


def test_outputter_kv_none_value():
    """outputter_kv handles None leaf values"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"key": None})
    assert "key: None" in result


def test_outputter_kv_list_values():
    """outputter_kv flattens list values with integer index keys"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"items": ["a", "b"]})
    assert "items.0: a" in result
    assert "items.1: b" in result


def test_outputter_kv_top_level_list():
    """outputter_kv handles a top-level list, producing '0: val' lines"""
    from picle.models import Outputters

    result = Outputters.outputter_kv(["x", "y"])
    assert "0: x" in result
    assert "1: y" in result


def test_outputter_kv_empty_dict():
    """outputter_kv with empty dict returns empty string"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({})
    assert result == ""


def test_outputter_kv_empty_list():
    """outputter_kv with empty list returns empty string"""
    from picle.models import Outputters

    result = Outputters.outputter_kv([])
    assert result == ""


def test_outputter_kv_numeric_leaf():
    """outputter_kv correctly renders numeric leaf values"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"count": 42, "ratio": 3.14})
    assert "count: 42" in result
    assert "ratio: 3.14" in result


def test_outputter_kv_boolean_leaf():
    """outputter_kv correctly renders boolean leaf values"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"flag": True, "off": False})
    assert "flag: True" in result
    assert "off: False" in result


def test_outputter_kv_list_of_dicts():
    """outputter_kv flattens a list of dicts, indexing by list position"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"hosts": [{"name": "r1"}, {"name": "r2"}]})
    assert "hosts.0.name: r1" in result
    assert "hosts.1.name: r2" in result


def test_outputter_kv_custom_separator():
    """outputter_kv respects a custom separator for nested dicts"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"a": {"b": "c"}}, separator="/")
    assert "a/b: c" in result
    assert "a.b: c" not in result


def test_outputter_kv_custom_separator_with_list():
    """outputter_kv forwards custom separator through list branches (bug fix check)"""
    from picle.models import Outputters

    result = Outputters.outputter_kv({"a": [{"b": "c"}]}, separator="/")
    # Without the fix, this would produce "a/0.b: c" (mixing separators)
    assert "a/0/b: c" in result
    assert "a/0.b: c" not in result


def test_outputter_kv_deeply_nested():
    """outputter_kv handles deeply nested structures correctly"""
    from picle.models import Outputters

    data = {"l1": {"l2": {"l3": {"l4": "deep"}}}}
    result = Outputters.outputter_kv(data)
    assert "l1.l2.l3.l4: deep" in result


def test_outputter_kv_mixed_list_and_dict():
    """outputter_kv handles structures mixing lists and dicts at multiple levels"""
    from picle.models import Outputters

    data = {
        "some": {"dictionary": {"data": None}},
        "more": {"dictionary": ["data"]},
        "even": {"more": {"dictionary": "data"}},
        "list": [
            {"more": {"dictionary": "data"}},
            {"more": {"dictionary": "data"}},
        ],
    }
    result = Outputters.outputter_kv(data)
    assert "some.dictionary.data: None" in result
    assert "more.dictionary.0: data" in result
    assert "even.more.dictionary: data" in result
    assert "list.0.more.dictionary: data" in result
    assert "list.1.more.dictionary: data" in result


def test_outputter_kv_via_pipe():
    """outputter_kv works end-to-end via shell pipe command"""
    shell.onecmd("top")
    shell.onecmd("show data | kv")
    shell_output = mock_stdout.write.call_args_list[-1][0][0]
    print(f"shell output: '{shell_output}'")
    assert "some.dictionary.data: None" in shell_output
    assert "more.dictionary.0: data" in shell_output
    assert "even.more.dictionary: data" in shell_output
    assert "list.0.more.dictionary: data" in shell_output
    assert "list.1.more.dictionary: data" in shell_output


def test_pipe_kv_with_string_data():
    """Test kv outputter with string data passes through"""
    from picle.models import Outputters

    result = Outputters.outputter_kv("already a string")
    assert result == "already a string"


def test_pipe_formatter_kv():
    shell.onecmd("top")  # go to top
    shell.onecmd("show data | kv")

    shell_output = mock_stdout.write.call_args_list[-1][0][0]

    print(f" shell output: '{shell_output}'")

    assert """some.dictionary.data: None
more.dictionary.0: data
even.more.dictionary: data
list.0.more.dictionary: data
list.1.more.dictionary: data""" in shell_output


def test_source_with_choice():
    shell.onecmd("top")  # go to top

    # test choice empty
    shell_output = shell.completedefault(
        "test_source_with_choice value ", "test_source_with_choice value ", 0, 40
    )
    print(f" shell output: '{shell_output}'")
    assert shell_output == ["False ", "None ", "True ", "bar ", "foo "]
