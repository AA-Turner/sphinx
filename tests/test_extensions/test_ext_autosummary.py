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
        assert public == ['Path', 'Union', 'Foo']
        assert items == ['Path', 'Union', 'Foo', '_Baz']
    else:
        assert public == ['Path', 'Foo']
        assert items == ['Path', 'Foo', '_Baz']
