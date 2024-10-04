from __future__ import annotations

from collections import namedtuple
from queue import Queue
from pathlib import Path
from threading import Thread
from unittest import mock

from sphinx.util import requests

CHECK_IMMEDIATELY = 0
QUEUE_POLL_SECS = 1
CheckResult = namedtuple('CheckResult', ['uri', 'status', 'message', 'code'])


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

    def __init__(self, rqueue: Queue[CheckResult], wqueue: Queue[str | None]) -> None:
        self.rqueue = rqueue
        self.wqueue = wqueue
        self._session = requests._Session()
        super().__init__(daemon=True)

    def run(self) -> None:
        while True:
            uri = self.wqueue.get()
            if not uri:
                # An empty hyperlink is a signal to shutdown the worker; cleanup resources here
                self._session.close()
                break

            status, info, code = self._check_uri(uri)
            self.rqueue.put(CheckResult(uri, status, info, code))
            self.wqueue.task_done()

    def _check_uri(self, req_url: str) -> tuple[str, str, int]:
        error_message = ''
        for retrieval_method, kwargs in [
            (self._session.head, {'allow_redirects': True}),
            (self._session.get, {'stream': True}),
        ]:
            try:
                response = retrieval_method(
                    url=req_url,
                    auth=None,
                    headers={},
                    timeout=30,
                    **kwargs,
                    _user_agent=None,
                    _tls_info=(True, None),
                )
                # Copy data we need from the (closed) response
                response.raise_for_status()
                del response
                break
            except Exception as err:
                return 'broken', str(err), 0
        return 'broken', error_message, 0


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
        rqueue: Queue[CheckResult] = Queue()
        workers: list[HyperlinkAvailabilityCheckWorker] = []
        wqueue: Queue[str | None] = Queue()

        # invoke threads
        num_workers = 5
        for _i in range(num_workers):
            thread = HyperlinkAvailabilityCheckWorker(rqueue, wqueue)
            thread.start()
            workers.append(thread)

        # check
        total_links = 0
        for hyperlink in HYPERLINKS:
            wqueue.put(hyperlink, False)
            total_links += 1

        done = 0
        while done < total_links:
            result = rqueue.get()
            print(result)
            done += 1

        # shutdown_threads
        wqueue.join()
        for _worker in workers:
            wqueue.put('', False)
