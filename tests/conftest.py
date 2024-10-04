from __future__ import annotations

import sys

import docutils
import pytest

import sphinx
import sphinx.locale
import sphinx.pycode

pytest_plugins = ['sphinx.testing.fixtures']

# Exclude 'roots' dirs for pytest test collector
collect_ignore = ['test-root']


def pytest_report_header(config: pytest.Config) -> str:
    header = f'libraries: Sphinx-{sphinx.__display_version__}, docutils-{docutils.__version__}'
    if sys.version_info[:2] >= (3, 13):
        header += f'\nGIL enabled?: {sys._is_gil_enabled()}'
    if hasattr(config, '_tmp_path_factory'):
        header += f'\nbase tmp_path: {config._tmp_path_factory.getbasetemp()}'
    return header
