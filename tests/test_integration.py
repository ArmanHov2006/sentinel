"""Integration tests for the full chat pipeline."""

import os
from unittest.mock import patch

from fastapi.testclient import TestClient


def _create_test_app():
    """Create a test app with mocked heavy dependencies."""
    with (
        patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
                "SENTINEL_ENV": "test",
                "REQUIRE_AUTH": "false",
            },
        ),
        patch("sentinel.core.config.get_settings") as mock_settings,
    ):
        from sentinel.core.config import Settings

        settings = Settings(
            openai_api_key="",
            anthropic_api_key="",
            sentinel_env="test",
            require_auth=False,
        )
        mock_settings.return_value = settings

        from sentinel.main import app

        return app


app = _create_test_app()
client = TestClient(app)


class TestHealthEndpoint:
    def test_returns_valid_status(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("healthy", "degraded", "unhealthy")
        assert data["version"] == "0.1.0"
        assert "checks" in data


class TestChatPipeline:
    def test_basic_completion_mock_fallback(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello"}],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["object"] == "chat.completion"
        assert "You said:" in data["choices"][0]["message"]["content"]

    def test_streaming_mock_fallback(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hello"}],
            "stream": True,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]

        content = resp.text
        assert "data: " in content
        assert "data: [DONE]" in content

    def test_validation_rejects_invalid_role(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "invalid", "content": "Hi"}],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 422

    def test_validation_rejects_missing_messages(self):
        payload = {"model": "gpt-4o-mini"}
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 422

    def test_validation_rejects_bad_temperature(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hi"}],
            "temperature": 5.0,
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 422

    def test_request_id_in_response_headers(self):
        payload = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": "Hi"}],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert "x-request-id" in resp.headers

    def test_multiple_messages(self):
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi!"},
                {"role": "user", "content": "How are you?"},
            ],
        }
        resp = client.post("/v1/chat/completions", json=payload)
        assert resp.status_code == 200
        assert "How are you?" in resp.json()["choices"][0]["message"]["content"]


class TestDashboard:
    def test_root_redirects(self):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 307
