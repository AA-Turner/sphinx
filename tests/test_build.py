from queue import Queue
from threading import Thread

import requests

_USER_AGENT = (
    'Mozilla/5.0 (X11; Linux x86_64; rv:100.0) Gecko/20100101 Firefox/100.0 '
    'Sphinx/8.0.2'
)


class HyperlinkAvailabilityCheckWorker(Thread):
    def __init__(self, rqueue: Queue[str], wqueue: Queue[str | None]) -> None:
        self.rqueue = rqueue
        self.wqueue = wqueue
        self._session = requests.Session()
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
                    timeout=30,
                    allow_redirects=True,
                    verify=True,
                    headers={'User-Agent': _USER_AGENT},
                )
                response.raise_for_status()
                del response
            except Exception:
                pass
            self.rqueue.put(uri)
            self.wqueue.task_done()


def test_build_all():
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
