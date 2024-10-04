from queue import Queue
from threading import Thread
from unittest import mock

from sphinx.util import requests


class HyperlinkAvailabilityCheckWorker(Thread):
    def __init__(self, rqueue: Queue[str], wqueue: Queue[str | None]) -> None:
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

            try:
                response = self._session.head(
                    url=uri,
                    auth=None,
                    headers={},
                    timeout=30,
                    allow_redirects=True,
                    _user_agent=None,
                    _tls_info=(True, None),
                )
                # Copy data we need from the (closed) response
                response.raise_for_status()
                del response
            except Exception:
                pass
            self.rqueue.put(uri)
            self.wqueue.task_done()


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
        rqueue: Queue[str] = Queue()
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
        for hyperlink in (
            'https://bugs.python.org/issue1000',
            'https://python.org/dev/',
            'https://bugs.python.org/issue1042',
            'https://peps.python.org/pep-0008/',
            'https://datatracker.ietf.org/doc/html/rfc1.html',
            'https://www.google.com',
        ):
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
