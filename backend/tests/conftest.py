import pytest
from fastapi.testclient import TestClient

import app.config as config
from app.api import deps
from app.config import Settings
from app.main import create_app


def _clear_dependency_caches() -> None:
    if hasattr(config.get_settings, "cache_clear"):
        config.get_settings.cache_clear()
    deps.get_storage_service.cache_clear()
    deps.get_job_repository.cache_clear()
    deps.get_upload_service.cache_clear()
    deps.get_generation_service.cache_clear()
    deps.get_job_service.cache_clear()
    deps.get_job_runner.cache_clear()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        storage_root=tmp_path / "storage",
        public_base_url="http://testserver",
        cors_origins=["http://localhost:5173"],
        job_simulation_seconds=0.4,
    )


@pytest.fixture
def client(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    _clear_dependency_caches()
    monkeypatch.setattr(config, "get_settings", lambda: settings)
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
    _clear_dependency_caches()
