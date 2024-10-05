"""Test the autodoc extension.  This tests mainly for config variables"""

from __future__ import annotations

from unittest.mock import Mock

import pytest

# NEVER import those objects from sphinx.ext.autodoc directly
from sphinx.ext.autodoc.directive import DocumenterBridge, process_documenter_options
from sphinx.util.docutils import LoggingReporter


@pytest.mark.sphinx('html', testroot='ext-autodoc')
def test_autodoc_class_signature_separated_new(app):
    app.config.autodoc_class_signature = 'separated'
    options = {
        'members': None,
        'undoc-members': None,
    }
    app.env.temp_data.setdefault('docname', 'index')  # set dummy docname
    doccls = app.registry.documenters['class']
    docoptions = process_documenter_options(doccls, app.config, options)
    state = Mock()
    state.document.settings.tab_width = 8
    bridge = DocumenterBridge(app.env, LoggingReporter(''), docoptions, 1, state)
    documenter = doccls(bridge, 'target.classes.Baz')
    documenter.generate()
    actual = bridge.result

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
