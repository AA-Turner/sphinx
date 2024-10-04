import queue
import threading

import requests


class HyperlinkAvailabilityCheckWorker(threading.Thread):
    def __init__(self, rqueue, wqueue) -> None:
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
                response = self._session.request(
                    'HEAD',
                    url=uri,
                    timeout=30,
                    verify=True,
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
        rqueue = queue.Queue()
        wqueue = queue.Queue()
        workers: list[HyperlinkAvailabilityCheckWorker] = []

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


if __name__ == '__main__':
    import sys

    print(f'GIL enabled?: {sys._is_gil_enabled()}')
    print()
    test_build_all()
