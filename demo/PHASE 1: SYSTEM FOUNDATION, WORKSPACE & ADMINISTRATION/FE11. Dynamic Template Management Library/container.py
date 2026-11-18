import time

from .config import Settings
from .events import EventBus
from .services import Audit, AuthService, BindingService, TemplateService
from .store import Store


class Container:
    def __init__(self, settings=None, clock=None, publisher=None, resolver=None, membership=None):
        self.settings = settings or Settings()
        self.clock = clock or time.time
        self.store = Store(self.settings.db_path)
        self.bus = EventBus(publisher)
        self.audit = Audit(self.store, self.clock)
        self.auth = AuthService(self.settings, self.clock, resolver)
        self.templates = TemplateService(self.settings, self.store, self.audit, self.bus, self.clock, membership)
        self.bindings = BindingService(self.store, self.templates, self.audit, self.bus, self.clock)
