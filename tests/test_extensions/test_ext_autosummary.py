"""Test the autosummary extension."""

from __future__ import annotations

import sys

import pytest

from sphinx.ext.autodoc import ModuleDocumenter
from sphinx.ext.autosummary import _get_documenter
from sphinx.ext.autosummary.generate import _get_all_members, _skip_member


@pytest.mark.sphinx('html', testroot='ext-autosummary', copy_test_root=True)
def test_autosummary_generate_content_for_module_imported_members(app):
    import autosummary_dummy_module

    obj = autosummary_dummy_module
    public: list[str] = []
    items: list[str] = []

    all_members = _get_all_members(ModuleDocumenter, obj, config=app.config)
    for name, value in all_members.items():
        documenter = _get_documenter(value, obj, registry=app.registry)
        if documenter.objtype == 'class':
            # skip imported members if expected
            skipped = _skip_member(value, name, documenter.objtype, events=app.events)
            if skipped is True:
                pass
            elif skipped is False:
                # show the member forcedly
                items.append(name)
                public.append(name)
            else:
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
