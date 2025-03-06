from __future__ import annotations

import sys
from pathlib import Path
from typing import Union


class Foo:
    pass


class _Baz:
    pass


class Exc(Exception):
    pass


class _Exc(Exception):
    pass


def test_autosummary_generate_content_for_module_imported_members():
    assert isinstance(Path, type)
    assert not issubclass(Path, BaseException)
    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert isinstance(Union, type)
    else:
        assert not isinstance(Union, type)
    assert not issubclass(Union, BaseException)
    assert isinstance(Foo, type)
    assert not issubclass(Foo, BaseException)
    assert isinstance(_Baz, type)
    assert not issubclass(_Baz, BaseException)
