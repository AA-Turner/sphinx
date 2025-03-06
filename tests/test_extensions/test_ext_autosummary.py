"""Test the autosummary extension."""

from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from sphinx.ext.autosummary import _get_documenter
from sphinx.ext.autosummary.generate import setup_documenters
from sphinx.registry import SphinxComponentRegistry
from sphinx.util.inspect import safe_getattr


def test_autosummary_generate_content_for_module_imported_members(app):
    import autosummary_dummy_module

    registry = SphinxComponentRegistry()
    app = SimpleNamespace(registry=registry)
    setup_documenters(app)

    obj = autosummary_dummy_module
    public: list[str] = []
    items: list[str] = []

    all_members = {}
    for name in dir(obj):
        try:
            all_members[name] = safe_getattr(obj, name)
        except AttributeError:
            continue
    for name, value in all_members.items():
        documenter = _get_documenter(value, obj, registry=registry)
        if documenter.objtype == 'class':
            items.append(name)
            if not name.startswith('_'):
                # considers member as public
                public.append(name)

    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert public == ['Class', 'Foo', 'Union']
        assert items == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert public == ['Class', 'Foo']
        assert items == ['Class', 'Foo', '_Baz']
