from __future__ import annotations

import contextlib
import re
import time
from os import path
from queue import PriorityQueue, Queue
from pathlib import Path
from threading import Thread
from typing import TYPE_CHECKING, NamedTuple
from urllib.parse import unquote, urlsplit
from unittest import mock

from requests.exceptions import ConnectionError, HTTPError, SSLError, TooManyRedirects
from requests.exceptions import Timeout

from sphinx.util import requests

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from requests import Response

# matches to foo:// and // (a protocol relative URL)
uri_re = re.compile('([a-z]+:)?//')

DEFAULT_REQUEST_HEADERS = {
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
}
CHECK_IMMEDIATELY = 0
QUEUE_POLL_SECS = 1
DEFAULT_DELAY = 60.0


class CheckRequest(NamedTuple):
    next_check: float
    hyperlink: str | None


class CheckResult(NamedTuple):
    uri: str
    status: str
    message: str
    code: int


class RateLimit(NamedTuple):
    delay: float
    next_check: float


TEST_ROOT = Path(__file__).parent.resolve() / 'test-root'
HYPERLINKS = [
    'https://bugs.python.org/issue1000',
    'https://python.org/dev/',
    'https://bugs.python.org/issue1042',
    'https://peps.python.org/pep-0008/',
    'https://datatracker.ietf.org/doc/html/rfc1.html',
    'https://www.google.com',
]


class HyperlinkAvailabilityCheckWorker(Thread):
    """A worker class for checking the availability of hyperlinks."""

    def __init__(
        self,
        rqueue: Queue[CheckResult],
        wqueue: Queue[CheckRequest],
        rate_limits: dict[str, RateLimit],
    ) -> None:
        self.rate_limits = rate_limits
        self.rqueue = rqueue
        self.wqueue = wqueue
        self._session = requests._Session()
        super().__init__(daemon=True)

    def run(self) -> None:
        while True:
            next_check, uri = self.wqueue.get()
            if uri is None:
                # An empty hyperlink is a signal to shutdown the worker; cleanup resources here
                self._session.close()
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
                self.wqueue.put(CheckRequest(next_check, uri), False)
                self.wqueue.task_done()
                continue
            status, info, code = self._check(uri)
            self.rqueue.put(CheckResult(uri, status, info, code))
            self.wqueue.task_done()

    def _check(self, uri: str) -> tuple[str, str, int]:
        # check for various conditions without bothering the network

        if len(uri) == 0 or uri.startswith(('#', 'mailto:', 'tel:')):
            return 'unchecked', '', 0
        if not uri.startswith(('http:', 'https:')):
            if uri_re.match(uri):
                # Non-supported URI schemes (ex. ftp)
                return 'unchecked', '', 0

            return 'broken', '', 0

        # need to actually check the URI
        status, info, code = self._check_uri(uri)
        return status, info, code

    def _retrieval_methods(
        self,
        check_anchors: bool,
        anchor: str,
    ) -> Iterator[tuple[Callable[..., Response], dict[str, bool]]]:
        if not check_anchors or not anchor:
            yield self._session.head, {'allow_redirects': True}
        yield self._session.get, {'stream': True}

    def _check_uri(self, uri: str) -> tuple[str, str, int]:
        req_url, delimiter, anchor = uri.partition('#')
        if delimiter and anchor:
            if re.match(r'^!', anchor):
                anchor = ''
            else:
                anchor = unquote(anchor)

        # handle non-ASCII URIs
        req_url.encode('ascii')

        auth_info = None

        # update request headers for the URL
        headers = _get_request_headers(uri, {})

        error_message = ''
        status_code = -1
        for retrieval_method, kwargs in self._retrieval_methods(True, anchor):
            try:
                response = retrieval_method(
                    url=req_url,
                    auth=auth_info,
                    headers=headers,
                    timeout=30,
                    **kwargs,
                    _user_agent=None,
                    _tls_info=(True, None),
                )
                # Copy data we need from the (closed) response
                status_code = response.status_code
                redirect_status_code = (
                    response.history[-1].status_code if response.history else None
                )  # NoQA: E501
                retry_after = response.headers.get('Retry-After', '')
                response_url = f'{response.url}'
                response.raise_for_status()
                del response
                break

            except Timeout as err:
                return 'timeout', str(err), 0

            except SSLError as err:
                # SSL failure; report that the link is broken.
                return 'broken', str(err), 0

            except (ConnectionError, TooManyRedirects) as err:
                # Servers drop the connection on HEAD requests, causing
                # ConnectionError.
                error_message = str(err)
                continue

            except HTTPError as err:
                if status_code in {401, 429, 503}:
                    return 'broken', str(err), 0
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
    candidates = (
        f'{url.scheme}://{url.netloc}',
        f'{url.scheme}://{url.netloc}/',
        uri,
        '*',
    )

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
    for i in range(1_000):
        print(f'loop: {i}')

        # setup
        rate_limits: dict[str, RateLimit] = {}
        rqueue: Queue[CheckResult] = Queue()
        workers: list[Thread] = []
        wqueue: PriorityQueue[CheckRequest] = PriorityQueue()

        # invoke threads
        num_workers = 5
        for _i in range(num_workers):
            thread = HyperlinkAvailabilityCheckWorker(rqueue, wqueue, rate_limits)
            thread.start()
            workers.append(thread)

        # check
        total_links = 0
        for hyperlink in HYPERLINKS:
            wqueue.put(CheckRequest(CHECK_IMMEDIATELY, hyperlink), False)
            total_links += 1

        done = 0
        while done < total_links:
            result = rqueue.get()
            print(result)
            done += 1

        # shutdown_threads
        wqueue.join()
        for _worker in workers:
            wqueue.put(CheckRequest(CHECK_IMMEDIATELY, None), False)
