"""Continuous acquisition/DSP with a bounded latest-result GUI mailbox.

The worker consumes every frame independently of rendering. Only display
updates can be replaced; the underlying iterator owns raw capture and logging.
"""
import queue
import threading


class LiveResults:
    def __init__(self, results):
        self.results = results
        self.mailbox = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.done = threading.Event()
        self.error = None
        self.thread = threading.Thread(target=self._run, name='radar-live-processing', daemon=True)
        self.thread.start()

    def _run(self):
        try:
            for result in self.results:
                if self.stop.is_set():
                    break
                if result is None:
                    continue
                try:
                    self.mailbox.put_nowait(result)
                except queue.Full:
                    try:
                        self.mailbox.get_nowait()
                    except queue.Empty:
                        pass
                    self.mailbox.put_nowait(result)
        except BaseException as error:
            self.error = error
        finally:
            try:
                self.results.close()
            except BaseException as error:
                self.error = self.error or error
            self.done.set()

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return self.mailbox.get(timeout=.05)
        except queue.Empty:
            if self.done.is_set():
                if self.error:
                    raise self.error
                raise StopIteration
            return None  # Main thread can pump GUI events while awaiting data.

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        if self.thread.is_alive():
            raise TimeoutError('Live acquisition worker did not stop within three seconds')
