"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

# NEVER import those objects from sphinx.ext.autodoc directly
from sphinx.ext.autodoc.directive import DocumenterBridge, process_documenter_options
from sphinx.util.docutils import LoggingReporter

if TYPE_CHECKING:
    from typing import Any

    from docutils.statemachine import StringList

    from sphinx.application import Sphinx


def do_autodoc(
    app: Sphinx,
    objtype: str,
    name: str,
    options: dict[str, Any] | None = None,
) -> StringList:
    options = {} if options is None else options.copy()
    app.env.temp_data.setdefault('docname', 'index')  # set dummy docname
    doccls = app.registry.documenters[objtype]
    docoptions = process_documenter_options(doccls, app.config, options)
    state = Mock()
    state.document.settings.tab_width = 8
    bridge = DocumenterBridge(app.env, LoggingReporter(''), docoptions, 1, state)
    documenter = doccls(bridge, name)
    documenter.generate()
    return bridge.result



@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_autodoc_class_signature_separated_init(app):
    app.config.autodoc_class_signature = 'separated'
    options = {
        'members': None,
        'undoc-members': None,
    }
    actual = do_autodoc(app, 'class', 'target.classes.Bar', options)
    assert list(actual) == [
        '',
        '.. py:class:: Bar',
        '   :module: target.classes',
        '',
        '',
        '   .. py:method:: Bar.__init__(x, y)',
        '      :module: target.classes',
        '',
    ]


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_autodoc_class_signature_separated_new(app):
    app.config.autodoc_class_signature = 'separated'
    options = {
        'members': None,
        'undoc-members': None,
    }
    actual = do_autodoc(app, 'class', 'target.classes.Baz', options)
    assert list(actual) == [
        '',
        '.. py:class:: Baz',
        '   :module: target.classes',
        '',
        '',
        '   .. py:method:: Baz.__new__(cls, x, y)',
        '      :module: target.classes',
        '      :staticmethod:',
        '',
    ]
