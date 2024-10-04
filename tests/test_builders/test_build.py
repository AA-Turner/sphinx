"""Test all builders."""

import os
import shutil
from contextlib import contextmanager
from unittest import mock

import pytest
from docutils import nodes

from sphinx.cmd.build import build_main
from sphinx.errors import SphinxError

from tests.utils import TESTS_ROOT


def request_session_head(url, **kwargs):
    response = mock.Mock()
    response.status_code = 200
    response.url = url
    return response


@pytest.fixture
def nonascii_srcdir(request, rootdir, sphinx_test_tempdir):
    # Build in a non-ASCII source dir
    test_name = '\u65e5\u672c\u8a9e'
    basedir = sphinx_test_tempdir / request.node.originalname
    srcdir = basedir / test_name
    if not srcdir.exists():
        shutil.copytree(rootdir / 'test-root', srcdir)

    # add a doc with a non-ASCII file name to the source dir
    (srcdir / (test_name + '.txt')).write_text(
        """
nonascii file name page
=======================
""",
        encoding='utf8',
    )

    root_doc = srcdir / 'index.txt'
    root_doc.write_text(
        root_doc.read_text(encoding='utf8')
        + f"""
.. toctree::

{test_name}/{test_name}
""",
        encoding='utf8',
    )
    return srcdir


@mock.patch(
    'sphinx.builders.linkcheck.requests.head',
    side_effect=request_session_head,
)
def test_build_all(make_app, nonascii_srcdir):
    for _ in range(1_000):
        app = make_app('linkcheck', srcdir=nonascii_srcdir)
        app.build()
