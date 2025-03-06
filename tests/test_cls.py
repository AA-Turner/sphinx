from __future__ import annotations

import sys
from pathlib import Path
from typing import Union

import pytest


class Foo:
    pass


class _Baz:
    pass


class Exc(Exception):
    pass


class _Exc(Exception):
    pass


def test_class():
    assert isinstance(Path, type)
    assert not issubclass(Path, BaseException)
    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert isinstance(Union, type)
        assert not issubclass(Union, BaseException)
    else:
        assert not isinstance(Union, type)
        with pytest.raises(TypeError):
            issubclass(Union, BaseException)
    assert isinstance(Foo, type)
    assert not issubclass(Foo, BaseException)
    assert isinstance(_Baz, type)
    assert not issubclass(_Baz, BaseException)
