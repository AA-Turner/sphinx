from __future__ import annotations

import sys

from tests.conftest import _TESTS_ROOT

sys.path.insert(0, str(_TESTS_ROOT / 'roots/test-ext-autosummary'))


def test_autosummary_generate_content_for_module_imported_members():
    import autosummary_dummy_module as obj

    public: list[str] = []
    items: list[str] = []

    for name in frozenset(dir(obj)):
        if isinstance(getattr(obj, name, None), type):
            items.append(name)
            if not name.startswith('_'):
                public.append(name)

    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert public == ['Class', 'Foo', 'Union']
        assert items == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert public == ['Class', 'Foo']
        assert items == ['Class', 'Foo', '_Baz']
