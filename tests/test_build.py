from __future__ import annotations

import contextlib
import re
import time
from os import path
from queue import PriorityQueue, Queue
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import unquote, urlsplit
from unittest import mock

from requests.exceptions import ConnectionError, HTTPError, SSLError, TooManyRedirects
from requests.exceptions import Timeout as RequestTimeout

# from sphinx.builders.linkcheck import Hyperlink, HyperlinkAvailabilityChecker
from sphinx.util import requests

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from requests import Response

uri_re = re.compile('([a-z]+:)?//')  # matches to foo:// and // (a protocol relative URL)

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
}
CHECK_IMMEDIATELY = 0
QUEUE_POLL_SECS = 1
DEFAULT_DELAY = 60.0

class Hyperlink(NamedTuple):
    uri: str
    docname: str
    docpath: Path
    lineno: int


class CheckRequest(NamedTuple):
    next_check: float
    hyperlink: Hyperlink | None


class CheckResult(NamedTuple):
    uri: str
    docname: str
    lineno: int
    status: str
    message: str
    code: int


class RateLimit(NamedTuple):
    delay: float
    next_check: float


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
    'https://www.google.com': Hyperlink(
        uri='https://www.google.com',
        docname='markup',
        docpath=TEST_ROOT / 'markup.txt',
        lineno=327,
    ),
}


class HyperlinkAvailabilityChecker:
    def __init__(self, config) -> None:
        self.config = config
        self.rate_limits: dict[str, RateLimit] = {}
        self.rqueue: Queue[CheckResult] = Queue()
        self.workers: list[Thread] = []
        self.wqueue: PriorityQueue[CheckRequest] = PriorityQueue()
        self.num_workers: int = config.linkcheck_workers

        self.to_ignore: list[re.Pattern[str]] = list(map(re.compile,
                                                         self.config.linkcheck_ignore))

    def check(self, hyperlinks: dict[str, Hyperlink]) -> Iterator[CheckResult]:
        self.invoke_threads()

        total_links = 0
        for hyperlink in hyperlinks.values():
            if self.is_ignored_uri(hyperlink.uri):
                yield CheckResult(hyperlink.uri, hyperlink.docname, hyperlink.lineno,
                                  'ignored', '', 0)
            else:
                self.wqueue.put(CheckRequest(CHECK_IMMEDIATELY, hyperlink), False)
                total_links += 1

        done = 0
        while done < total_links:
            yield self.rqueue.get()
            done += 1

        self.shutdown_threads()

    def invoke_threads(self) -> None:
        for _i in range(self.num_workers):
            thread = HyperlinkAvailabilityCheckWorker(self.config,
                                                      self.rqueue, self.wqueue,
                                                      self.rate_limits)
            thread.start()
            self.workers.append(thread)

    def shutdown_threads(self) -> None:
        self.wqueue.join()
        for _worker in self.workers:
            self.wqueue.put(CheckRequest(CHECK_IMMEDIATELY, None), False)

    def is_ignored_uri(self, uri: str) -> bool:
        return any(pat.match(uri) for pat in self.to_ignore)


class HyperlinkAvailabilityCheckWorker(Thread):
    """A worker class for checking the availability of hyperlinks."""

    def __init__(self, config,
                 rqueue: Queue[CheckResult],
                 wqueue: Queue[CheckRequest],
                 rate_limits: dict[str, RateLimit]) -> None:
        self.rate_limits = rate_limits
        self.rqueue = rqueue
        self.wqueue = wqueue

        self.anchors_ignore: list[re.Pattern[str]] = list(
            map(re.compile, config.linkcheck_anchors_ignore))
        self.anchors_ignore_for_url: list[re.Pattern[str]] = list(
            map(re.compile, config.linkcheck_anchors_ignore_for_url))
        self.documents_exclude: list[re.Pattern[str]] = list(
            map(re.compile, config.linkcheck_exclude_documents))
        self.auth = [(re.compile(pattern), auth_info) for pattern, auth_info
                     in config.linkcheck_auth]

        self.timeout: int | float | None = config.linkcheck_timeout
        self.request_headers: dict[str, dict[str, str]] = config.linkcheck_request_headers
        self.check_anchors: bool = config.linkcheck_anchors
        self.allowed_redirects: dict[re.Pattern[str], re.Pattern[str]]
        self.allowed_redirects = config.linkcheck_allowed_redirects
        self.retries: int = config.linkcheck_retries
        self.rate_limit_timeout = config.linkcheck_rate_limit_timeout
        self._allow_unauthorized = config.linkcheck_allow_unauthorized
        if config.linkcheck_report_timeouts_as_broken:
            self._timeout_status = 'broken'
        else:
            self._timeout_status = 'timeout'

        self.user_agent = config.user_agent
        self.tls_verify = config.tls_verify
        self.tls_cacerts = config.tls_cacerts

        self._session = requests._Session()

        super().__init__(daemon=True)

    def run(self) -> None:
        while True:
            next_check, hyperlink = self.wqueue.get()
            if hyperlink is None:
                # An empty hyperlink is a signal to shutdown the worker; cleanup resources here
                self._session.close()
                break

            uri, docname, _docpath, lineno = hyperlink
            if uri is None:
                break

            netloc = urlsplit(uri).netloc
            with contextlib.suppress(KeyError):
                # Refresh rate limit.
                # When there are many links in the queue, workers are all stuck waiting
                # for responses, but the builder keeps queuing. Links in the queue may
                # have been queued before rate limits were discovered.
                next_check = self.rate_limits[netloc].next_check
            if next_check > time.time():
                # Sleep before putting message back in the queue to avoid
                # waking up other threads.
                time.sleep(QUEUE_POLL_SECS)
                self.wqueue.put(CheckRequest(next_check, hyperlink), False)
                self.wqueue.task_done()
                continue
            status, info, code = self._check(docname, uri, hyperlink)
            self.rqueue.put(CheckResult(uri, docname, lineno, status, info, code))
            self.wqueue.task_done()

    def _check(self, docname: str, uri: str, hyperlink: Hyperlink) -> tuple[str, str, int]:
        # check for various conditions without bothering the network

        for doc_matcher in self.documents_exclude:
            if doc_matcher.match(docname):
                info = (
                    f'{docname} matched {doc_matcher.pattern} from '
                    'linkcheck_exclude_documents'
                )
                return 'ignored', info, 0

        if len(uri) == 0 or uri.startswith(('#', 'mailto:', 'tel:')):
            return 'unchecked', '', 0
        if not uri.startswith(('http:', 'https:')):
            if uri_re.match(uri):
                # Non-supported URI schemes (ex. ftp)
                return 'unchecked', '', 0

            src_dir = path.dirname(hyperlink.docpath)
            if path.exists(path.join(src_dir, uri)):
                return 'working', '', 0
            return 'broken', '', 0

        # need to actually check the URI
        status, info, code = '', '', 0
        for _ in range(self.retries):
            status, info, code = self._check_uri(uri, hyperlink)
            if status != 'broken':
                break

        return status, info, code

    def _retrieval_methods(
        self,
        check_anchors: bool,
        anchor: str,
    ) -> Iterator[tuple[Callable[..., Response], dict[str, bool]]]:
        if not check_anchors or not anchor:
            yield self._session.head, {'allow_redirects': True}
        yield self._session.get, {'stream': True}

    def _check_uri(self, uri: str, hyperlink: Hyperlink) -> tuple[str, str, int]:
        req_url, delimiter, anchor = uri.partition('#')
        if delimiter and anchor:
            for rex in self.anchors_ignore:
                if rex.match(anchor):
                    anchor = ''
                    break
            else:
                for rex in self.anchors_ignore_for_url:
                    if rex.match(req_url):
                        anchor = ''
                        break
            anchor = unquote(anchor)

        # handle non-ASCII URIs
        req_url.encode('ascii')

        # Get auth info, if any
        for pattern, auth_info in self.auth:  # NoQA: B007 (false positive)
            if pattern.match(uri):
                break
        else:
            auth_info = None

        # update request headers for the URL
        headers = _get_request_headers(uri, self.request_headers)

        # Linkcheck HTTP request logic:
        #
        # - Attempt HTTP HEAD before HTTP GET unless page content is required.
        # - Follow server-issued HTTP redirects.
        # - Respect server-issued HTTP 429 back-offs.
        error_message = ''
        status_code = -1
        response_url = retry_after = ''
        for retrieval_method, kwargs in self._retrieval_methods(self.check_anchors, anchor):
            try:
                response = retrieval_method(
                    url=req_url, auth=auth_info,
                    headers=headers,
                    timeout=self.timeout,
                    **kwargs,
                    _user_agent=self.user_agent,
                    _tls_info=(self.tls_verify, self.tls_cacerts),
                )
                # Copy data we need from the (closed) response
                status_code = response.status_code
                redirect_status_code = response.history[-1].status_code if response.history else None  # NoQA: E501
                retry_after = response.headers.get('Retry-After', '')
                response_url = f'{response.url}'
                response.raise_for_status()
                del response
                break

            except RequestTimeout as err:
                return self._timeout_status, str(err), 0

            except SSLError as err:
                # SSL failure; report that the link is broken.
                return 'broken', str(err), 0

            except (ConnectionError, TooManyRedirects) as err:
                # Servers drop the connection on HEAD requests, causing
                # ConnectionError.
                error_message = str(err)
                continue

            except HTTPError as err:
                error_message = str(err)

                # Unauthorized: the client did not provide required credentials
                if status_code == 401:
                    status = 'working' if self._allow_unauthorized else 'broken'
                    return status, 'unauthorized', 0

                # Rate limiting; back-off if allowed, or report failure otherwise
                if status_code == 429:
                    return 'broken', error_message, 0

                # Don't claim success/failure during server-side outages
                if status_code == 503:
                    return 'ignored', 'service unavailable', 0

                # For most HTTP failures, continue attempting alternate retrieval methods
                continue

            except Exception as err:
                # Unhandled exception (intermittent or permanent); report that
                # the link is broken.
                return 'broken', str(err), 0

        else:
            # All available retrieval methods have been exhausted; report
            # that the link is broken.
            return 'broken', error_message, 0

        # Success; clear rate limits for the origin
        netloc = urlsplit(req_url).netloc
        self.rate_limits.pop(netloc, None)

        if response_url.rstrip('/') == req_url.rstrip('/'):
            return 'working', '', 0
        elif redirect_status_code is not None:
            return 'redirected', response_url, redirect_status_code
        else:
            return 'redirected', response_url, 0


def _get_request_headers(
    uri: str,
    request_headers: dict[str, dict[str, str]],
) -> dict[str, str]:
    url = urlsplit(uri)
    candidates = (f'{url.scheme}://{url.netloc}',
                  f'{url.scheme}://{url.netloc}/',
                  uri,
                  '*')

    for u in candidates:
        if u in request_headers:
            return {**DEFAULT_REQUEST_HEADERS, **request_headers[u]}
    return {}


def request_session_head(url, **kwargs):
    response = mock.Mock()
    response.status_code = 200
    response.url = url
    return response


@mock.patch(
    'sphinx.util.requests.head',
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
