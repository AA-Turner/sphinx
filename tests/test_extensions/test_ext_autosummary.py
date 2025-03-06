"""Test the autosummary extension."""

from __future__ import annotations

import inspect
import sys

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


def _get_documenter(obj, parent):
    if inspect.ismodule(obj):
        # ModuleDocumenter.can_document_member always returns False
        return ModuleDocumenter

    # Construct a fake documenter for *parent*
    if parent is not None:
        parent_doc_cls = _get_documenter(parent, None)
    else:
        parent_doc_cls = ModuleDocumenter

    if hasattr(parent, '__name__'):
        parent_doc = parent_doc_cls(FakeDirective(), parent.__name__)
    else:
        parent_doc = parent_doc_cls(FakeDirective(), '')

    # Get the correct documenter class for *obj*
    classes = [
        cls for cls in DOCUMENTERS
        if cls.can_document_member(obj, '', False, parent_doc)
    ]
    if classes:
        classes.sort(key=lambda cls: cls.priority)
        return classes[-1]
    else:
        return DataDocumenter


def test_autosummary_generate_content_for_module_imported_members():
    import autosummary_dummy_module

    obj = autosummary_dummy_module
    public: list[str] = []
    items: list[str] = []

    all_members = {name: getattr(obj, name) for name in dir(obj)}
    for name, value in all_members.items():
        documenter = _get_documenter(value, obj)
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
