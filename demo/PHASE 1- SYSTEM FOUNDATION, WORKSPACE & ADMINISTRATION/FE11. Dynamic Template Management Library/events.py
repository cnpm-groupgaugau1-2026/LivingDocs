import json
import threading


class EventBus:
    def __init__(self, publisher=None):
        self.publisher = publisher
        self.published = []
        self._lock = threading.Lock()

    def publish(self, topic, message):
        with self._lock:
            self.published.append((topic, message))
        if self.publisher:
            self.publisher(topic, json.dumps(message))
