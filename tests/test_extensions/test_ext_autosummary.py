"""Test the autosummary extension."""

from __future__ import annotations

import sys
from contextlib import chdir
from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pytest
from docutils import nodes

from sphinx import addnodes
from sphinx.ext.autosummary import (
    autosummary_table,
    autosummary_toc,
    extract_summary,
    import_by_name,
    mangle_signature,
)
from sphinx.ext.autosummary.generate import (
    AutosummaryEntry,
    generate_autosummary_content,
    generate_autosummary_docs,
)
from sphinx.ext.autosummary.generate import main as autogen_main
from sphinx.testing.util import assert_node, etree_parse
from sphinx.util.docutils import new_document

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

html_warnfile = StringIO()


defaults = {
    'extensions': ['sphinx.ext.autosummary'],
    'autosummary_generate': True,
    'autosummary_generate_overwrite': False,
}


@pytest.fixture(autouse=True)
def _unload_target_module():
    sys.modules.pop('target', None)


@pytest.mark.sphinx('html', testroot='ext-autosummary', copy_test_root=True)
def test_autosummary_generate_content_for_module_skipped(app):
    import autosummary_dummy_module

    template = Mock()

    def skip_member(app, what, name, obj, skip, options):
        if name in {'Foo', 'bar', 'Exc'}:
            return True
        return None

    app.connect('autodoc-skip-member', skip_member)
    generate_autosummary_content(
        'autosummary_dummy_module',
        autosummary_dummy_module,
        None,
        template,
        None,
        False,
        False,
        {},
        config=app.config,
        events=app.events,
        registry=app.registry,
    )
    context = template.render.call_args[0][1]
    assert context['members'] == [
        'CONSTANT1',
        'CONSTANT2',
        '_Baz',
        '_Exc',
        '__all__',
        '__builtins__',
        '__cached__',
        '__doc__',
        '__file__',
        '__name__',
        '__package__',
        '_quux',
        'non_imported_member',
        'quuz',
        'qux',
    ]
    assert context['functions'] == []
    assert context['classes'] == []
    assert context['exceptions'] == []


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
