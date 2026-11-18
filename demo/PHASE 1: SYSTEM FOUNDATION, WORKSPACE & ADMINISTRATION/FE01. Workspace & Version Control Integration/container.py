from .config import Settings
from .events import EventBus
from .github_client import GitHubClient
from .services import AuthService, RepositoryService, WebhookService, WorkspaceService
from .store import Store


class Container:
    def __init__(self, settings=None, transport=None, publisher=None, store=None):
        self.settings = settings or Settings()
        self.store = store or Store(self.settings.db_path)
        self.github = GitHubClient(self.settings, transport)
        self.bus = EventBus(publisher)
        self.auth = AuthService(self.settings, self.store, self.github)
        self.workspaces = WorkspaceService(self.store)
        self.repos = RepositoryService(self.settings, self.store, self.github, self.bus, self.workspaces, self.auth)
        self.webhooks = WebhookService(self.settings, self.store, self.bus)
