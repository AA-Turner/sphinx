"""Test the autosummary extension."""

from __future__ import annotations

import sys
import types

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
from sphinx.ext.autosummary import FakeDirective

from tests.conftest import _TESTS_ROOT

sys.path.insert(0, str(_TESTS_ROOT / 'roots/test-ext-autosummary'))

DOCUMENTERS = (
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


def _is_class_documenter(obj):
    if isinstance(obj, types.ModuleType):
        # ModuleDocumenter.can_document_member always returns False
        return False

    # Construct a fake documenter for *parent*
    parent_doc = ModuleDocumenter(FakeDirective(), '')

    # Get the correct documenter class for *obj*
    return ClassDocumenter.can_document_member(obj, '', False, parent_doc)


def test_autosummary_generate_content_for_module_imported_members():
    import autosummary_dummy_module

    obj = autosummary_dummy_module
    assert isinstance(obj, types.ModuleType)
    public: list[str] = []
    items: list[str] = []

    all_members = {name: getattr(obj, name) for name in dir(obj)}
    for name, value in all_members.items():
        if _is_class_documenter(value):
            items.append(name)
            if not name.startswith('_'):
                public.append(name)

    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert public == ['Class', 'Foo', 'Union']
        assert items == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert public == ['Class', 'Foo']
        assert items == ['Class', 'Foo', '_Baz']
