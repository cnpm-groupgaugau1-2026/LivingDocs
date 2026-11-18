import json
import queue
import threading


class EventBus:
    def __init__(self, publisher=None):
        self.publisher = publisher
        self._q = queue.Queue()
        self._handlers = []
        self._lock = threading.Lock()
        self.published = []

    def subscribe(self, handler):
        self._handlers.append(handler)

    def publish(self, topic, message):
        with self._lock:
            self.published.append((topic, message))
        if self.publisher:
            self.publisher(topic, json.dumps(message))
        self._q.put((topic, message))

    def drain(self):
        handled = 0
        while True:
            try:
                topic, message = self._q.get_nowait()
            except queue.Empty:
                break
            for h in self._handlers:
                h(topic, message)
            handled += 1
        return handled
