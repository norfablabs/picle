"""Optional output libraries must not be required to import PICLE."""

import subprocess
import sys


def test_import_without_rich():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import importlib.abc
import sys

class WithoutRich(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'rich' or fullname.startswith('rich.'):
            raise ModuleNotFoundError('Rich disabled for optional dependency check')

sys.meta_path.insert(0, WithoutRich())
from picle import App, ChatSession
from picle.chat import HAS_RICH
assert HAS_RICH is False
""",
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
