"""Test the autosummary extension."""

from __future__ import annotations

import sys

import pytest

from sphinx.ext.autodoc import ModuleDocumenter
from sphinx.ext.autosummary.generate import _get_members


@pytest.mark.sphinx('html', testroot='ext-autosummary', copy_test_root=True)
def test_autosummary_generate_content_for_module_imported_members(app):
    import autosummary_dummy_module

    obj = autosummary_dummy_module
    classes, all_classes = _get_members(
        ModuleDocumenter,
        obj,
        {'class'},
        config=app.config,
        events=app.events,
        registry=app.registry,
        imported=True,
    )
    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert classes == ['Class', 'Foo', 'Union']
        assert all_classes == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert classes == ['Class', 'Foo']
        assert all_classes == ['Class', 'Foo', '_Baz']
