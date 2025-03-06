from __future__ import annotations

import sys
from typing import Union

from tests.conftest import _TESTS_ROOT

sys.path.insert(0, str(_TESTS_ROOT / 'roots/test-ext-autosummary'))

from autosummary_class_module import Class


class Foo:
    pass


class _Baz:
    pass


class Exc(Exception):
    pass


class _Exc(Exception):
    pass


def test_autosummary_generate_content_for_module_imported_members():
    public: list[str] = []
    items: list[str] = []

    ns = globals()
    for name in ns:
        value = ns.get(name)
        if isinstance(value, type) and not issubclass(value, BaseException):
            items.append(name)
            if not name.startswith('_'):
                public.append(name)

    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert public == ['Class', 'Foo', 'Union']
        assert items == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert public == ['Class', 'Foo']
        assert items == ['Class', 'Foo', '_Baz']
