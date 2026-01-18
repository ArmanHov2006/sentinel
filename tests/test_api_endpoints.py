"""Tests for FastAPI endpoints."""

import os
import sys
import pytest
import json
from fastapi.testclient import TestClient

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sentinel.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Test suite for health endpoint."""
    
    def test_health_endpoint(self):
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.1.0"
        assert "status" in data
        assert "version" in data


class TestChatCompletionNonStreaming:
    """Test suite for non-streaming chat completion endpoint."""
    
    def test_chat_completion_basic(self):
        """Basic chat completion should work."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Hello, world"}
            ],
            "stream": False
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert data["object"] == "chat.completion"
        assert data["model"] == "gpt-4"
        assert "id" in data
        assert data["id"].startswith("sentinel-")
        assert "created" in data
        assert len(data["choices"]) > 0
        assert data["choices"][0]["message"]["role"] == "assistant"
        assert "You said:" in data["choices"][0]["message"]["content"]
        assert data["choices"][0]["finish_reason"] == "stop"
        assert "usage" in data
        assert data["usage"]["total_tokens"] > 0
    
    def test_chat_completion_with_temperature(self):
        """Chat completion should accept temperature parameter."""
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": "Test message"}
            ],
            "temperature": 0.7,
            "stream": False
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "gpt-3.5-turbo"
    
    def test_chat_completion_multiple_messages(self):
        """Chat completion should handle multiple messages."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "system", "content": "You are a helpful assistant"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "user", "content": "How are you?"}
            ],
            "stream": False
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        data = response.json()
        # Should respond to the last user message
        assert "You said:" in data["choices"][0]["message"]["content"]
        assert "How are you?" in data["choices"][0]["message"]["content"]
    
    def test_chat_completion_invalid_model(self):
        """Chat completion should accept any model string."""
        payload = {
            "model": "invalid-model-name",
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": False
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["model"] == "invalid-model-name"


class TestChatCompletionStreaming:
    """Test suite for streaming chat completion endpoint."""
    
    def test_streaming_response_format(self):
        """Streaming response should be in SSE format."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Say hello"}
            ],
            "stream": True
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/event-stream; charset=utf-8"
    
    def test_streaming_content(self):
        """Streaming response should contain chunks."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": True
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        # Read streaming content
        content = b""
        for chunk in response.iter_bytes():
            content += chunk
        
        content_str = content.decode('utf-8')
        # Should have data: prefix
        assert "data: " in content_str
        # Should have [DONE] at the end
        assert "data: [DONE]" in content_str
    
    def test_streaming_chunks_format(self):
        """Streaming chunks should be valid JSON."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "user", "content": "Test"}
            ],
            "stream": True
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 200
        
        chunks_received = []
        for line in response.iter_lines():
            if line.startswith("data: "):
                data_str = line[6:]  # Remove "data: " prefix
                if data_str == "[DONE]":
                    break
                try:
                    chunk_data = json.loads(data_str)
                    if "choices" in chunk_data:
                        chunks_received.append(chunk_data)
                except json.JSONDecodeError:
                    pass
        
        # Should receive at least one chunk
        assert len(chunks_received) > 0
        # Each chunk should have choices with delta
        for chunk in chunks_received:
            assert "choices" in chunk
            assert len(chunk["choices"]) > 0
            assert "delta" in chunk["choices"][0]
            assert "content" in chunk["choices"][0]["delta"]


class TestValidation:
    """Test suite for request validation."""
    
    def test_missing_required_fields(self):
        """Request should fail if required fields are missing."""
        # Missing messages
        payload = {"model": "gpt-4"}
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422
    
    def test_invalid_message_format(self):
        """Request should validate message format."""
        payload = {
            "model": "gpt-4",
            "messages": [
                {"role": "invalid_role", "content": "Test"}
            ]
        }
        response = client.post("/v1/chat/completions", json=payload)
        # Should fail validation
        assert response.status_code == 422
    
    def test_temperature_validation(self):
        """Temperature should be validated within range."""
        # Temperature too high
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test"}],
            "temperature": 3.0
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422
        
        # Temperature too low (negative)
        payload = {
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Test"}],
            "temperature": -1.0
        }
        response = client.post("/v1/chat/completions", json=payload)
        assert response.status_code == 422


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
