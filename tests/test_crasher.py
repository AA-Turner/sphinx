"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

import inspect
import types
from functools import partial, partialmethod, singledispatchmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

    from typing_extensions import TypeIs


class Baz:
    def __new__(cls, x, y):
        pass


def test_crasher():
    obj = Baz.__new__
    inspect.isasyncgenfunction(obj)
