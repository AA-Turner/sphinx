from unittest import mock

import pytest


def request_session_head(url, **kwargs):
    response = mock.Mock()
    response.status_code = 200
    response.url = url
    return response


@mock.patch(
    'sphinx.builders.linkcheck.requests.head',
    side_effect=request_session_head,
)
@pytest.mark.sphinx('linkcheck')
def test_build_all(requests_head, app):
    for _ in range(1_000):
        app.build()
