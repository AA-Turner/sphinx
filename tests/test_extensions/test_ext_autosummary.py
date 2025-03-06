"""Test the autosummary extension."""

from __future__ import annotations

import sys
from unittest.mock import Mock

import pytest

from sphinx.ext.autodoc import ModuleDocumenter
from sphinx.ext.autosummary.generate import _get_members, generate_autosummary_content


@pytest.fixture(autouse=True)
def _unload_target_module():
    sys.modules.pop('target', None)


@pytest.mark.sphinx('html', testroot='ext-autosummary', copy_test_root=True)
def test_autosummary_generate_content_for_module_imported_members(app):
    import autosummary_dummy_module

    template = Mock()

    generate_autosummary_content(
        'autosummary_dummy_module',
        autosummary_dummy_module,
        None,
        template,
        None,
        True,
        False,
        {},
        config=app.config,
        events=app.events,
        registry=app.registry,
    )
    assert template.render.call_args[0][0] == 'module'

    context = template.render.call_args[0][1]
    assert context['members'] == [
        'CONSTANT1',
        'CONSTANT2',
        'Class',
        'Exc',
        'Foo',
        'Union',
        '_Baz',
        '_Exc',
        '__all__',
        '__builtins__',
        '__cached__',
        '__doc__',
        '__file__',
        '__loader__',
        '__name__',
        '__package__',
        '__spec__',
        '_quux',
        'bar',
        'considered_as_imported',
        'non_imported_member',
        'path',
        'quuz',
        'qux',
    ]
    assert context['functions'] == ['bar']
    assert context['all_functions'] == ['_quux', 'bar']
    if sys.version_info >= (3, 14, 0, 'alpha', 5):
        assert context['classes'] == ['Class', 'Foo', 'Union']
        assert context['all_classes'] == ['Class', 'Foo', 'Union', '_Baz']
    else:
        assert context['classes'] == ['Class', 'Foo']
        assert context['all_classes'] == ['Class', 'Foo', '_Baz']
    assert context['exceptions'] == ['Exc']
    assert context['all_exceptions'] == ['Exc', '_Exc']
    assert context['attributes'] == ['CONSTANT1', 'qux', 'quuz', 'non_imported_member']
    assert context['all_attributes'] == [
        'CONSTANT1',
        'qux',
        'quuz',
        'non_imported_member',
    ]
    assert context['fullname'] == 'autosummary_dummy_module'
    assert context['module'] == 'autosummary_dummy_module'
    assert context['objname'] == ''
    assert context['name'] == ''
    assert context['objtype'] == 'module'

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
