from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from sphinx.builders.linkcheck import Hyperlink, HyperlinkAvailabilityChecker

TEST_ROOT = Path(__file__).parent.resolve() / 'test-root'
HYPERLINKS = {
    'https://bugs.python.org/issue1000': Hyperlink(
        uri='https://bugs.python.org/issue1000',
        docname='extensions',
        docpath=TEST_ROOT / 'extensions.txt',
        lineno=7,
    ),
    'https://python.org/dev/': Hyperlink(
        uri='https://python.org/dev/',
        docname='extensions',
        docpath=TEST_ROOT / 'extensions.txt',
        lineno=7,
    ),
    'https://bugs.python.org/issue1042': Hyperlink(
        uri='https://bugs.python.org/issue1042',
        docname='extensions',
        docpath=TEST_ROOT / 'extensions.txt',
        lineno=7,
    ),
    '#some-label': Hyperlink(
        uri='#some-label',
        docname='index',
        docpath=TEST_ROOT / 'index.txt',
        lineno=65,
    ),
    'https://peps.python.org/pep-0008/': Hyperlink(
        uri='https://peps.python.org/pep-0008/',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=142,
    ),
    'https://datatracker.ietf.org/doc/html/rfc1.html': Hyperlink(
        uri='https://datatracker.ietf.org/doc/html/rfc1.html',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=144,
    ),
    '#envvar-HOME': Hyperlink(
        uri='#envvar-HOME',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=146,
    ),
    '#cmdoption-python-c': Hyperlink(
        uri='#cmdoption-python-c',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=167,
    ),
    '#ref1': Hyperlink(
        uri='#ref1',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=322,
    ),
    '#ref-1': Hyperlink(
        uri='#ref-1',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=322,
    ),
    'https://www.google.com': Hyperlink(
        uri='https://www.google.com',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=327,
    ),
    '#func_without_body': Hyperlink(
        uri='#func_without_body',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=434,
    ),
    '#module-mod': Hyperlink(
        uri='#module-mod',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=434,
    ),
    '#Time': Hyperlink(
        uri='#Time',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=434,
    ),
    '#bar.baz': Hyperlink(
        uri='#bar.baz',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=439,
    ),
    '#c.SphinxType': Hyperlink(
        uri='#c.SphinxType',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=440,
    ),
    '#userdesc-myobj': Hyperlink(
        uri='#userdesc-myobj',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=441,
    ),
    '#_CPPv4N1n5ArrayE': Hyperlink(
        uri='#_CPPv4N1n5ArrayE',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=442,
    ),
    '#cmdoption-perl-c': Hyperlink(
        uri='#cmdoption-perl-c',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=443,
    ),
}


def request_session_head(url, **kwargs):
    response = mock.Mock()
    response.status_code = 200
    response.url = url
    return response


@mock.patch(
    'sphinx.builders.linkcheck.requests.head',
    side_effect=request_session_head,
)
def test_build_all(requests_head):
    config = SimpleNamespace(
        tls_verify=True,
        tls_cacerts=None,
        user_agent=None,
        linkcheck_ignore=[],
        linkcheck_exclude_documents=[],
        linkcheck_allowed_redirects={},
        linkcheck_auth=[],
        linkcheck_request_headers={},
        linkcheck_retries=1,
        linkcheck_timeout=30,
        linkcheck_workers=5,
        linkcheck_anchors=True,
        linkcheck_anchors_ignore=['^!'],
        linkcheck_anchors_ignore_for_url=(),
        linkcheck_rate_limit_timeout=300.0,
        linkcheck_allow_unauthorized=False,
        linkcheck_report_timeouts_as_broken=False,
    )
    for i in range(1_000):
        print(f'loop: {i}')
        checker = HyperlinkAvailabilityChecker(config)
        for result in checker.check(HYPERLINKS):
            print(result)
