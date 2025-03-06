"""Test the autosummary extension."""

from __future__ import annotations

import sys
from types import SimpleNamespace

from sphinx.ext.autodoc import (
    AttributeDocumenter,
    ClassDocumenter,
    DataDocumenter,
    DecoratorDocumenter,
    ExceptionDocumenter,
    FunctionDocumenter,
    MethodDocumenter,
    ModuleDocumenter,
    PropertyDocumenter,
)
from sphinx.ext.autosummary import _get_documenter

from tests.conftest import _TESTS_ROOT

sys.path.insert(0, str(_TESTS_ROOT / 'roots/test-ext-autosummary'))


def test_autosummary_generate_content_for_module_imported_members():
    import autosummary_dummy_module

    registry = SimpleNamespace(documenters={
        documenter.objtype: documenter
        for documenter in (
            ModuleDocumenter,
            ClassDocumenter,
            ExceptionDocumenter,
            DataDocumenter,
            FunctionDocumenter,
            MethodDocumenter,
            AttributeDocumenter,
            DecoratorDocumenter,
            PropertyDocumenter,
        )
    })
    obj = autosummary_dummy_module
    public: list[str] = []
    items: list[str] = []

    all_members = {name: getattr(obj, name) for name in dir(obj)}
    for name, value in all_members.items():
        documenter = _get_documenter(value, obj, registry=registry)
        if documenter.objtype == 'class':
            items.append(name)
            if not name.startswith('_'):
                public.append(name)

    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert public == ['Class', 'Foo', 'Union']
        assert items == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert public == ['Class', 'Foo']
        assert items == ['Class', 'Foo', '_Baz']
