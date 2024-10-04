import shutil
from pathlib import Path
from unittest import mock

from sphinx.application import Sphinx


def request_session_head(url, **kwargs):
    response = mock.Mock()
    response.status_code = 200
    response.url = url
    return response


@mock.patch(
    'sphinx.builders.linkcheck.requests.head',
    side_effect=request_session_head,
)
def test_build_all(requests_head, tmp_path):
    test_root = Path(__file__).parent.resolve() / 'test-root'
    shutil.copytree(test_root, tmp_path, dirs_exist_ok=True)
    app = Sphinx(
        srcdir=tmp_path,
        confdir=tmp_path,
        outdir=tmp_path / '_build' / 'linkcheck',
        doctreedir=tmp_path / '_build' / 'doctrees',
        buildername='linkcheck',
    )
    for _ in range(1_000):
        app.build()
