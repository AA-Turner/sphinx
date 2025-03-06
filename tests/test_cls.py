from __future__ import annotations

import sys
import types
from typing import Union

import pytest


def test_class():
    assert isinstance(str | int, types.UnionType)
    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert isinstance(Union, type)
        assert not issubclass(Union, BaseException)
        assert isinstance(str | int, Union)
    else:
        assert not isinstance(Union, type)
        with pytest.raises(TypeError):
            issubclass(Union, BaseException)
