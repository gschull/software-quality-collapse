"""
Tests for the Quality Gate Dashboard FastAPI application.
"""
import os
import sqlite3
import tempfile
from fastapi.testclient import TestClient
import pytest


# Set up test environment before importing app
@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set test environment variables before app initialization."""
    os.environ["INGEST_TOKEN"] = "test-token-12345"


@pytest.fixture
def test_db():
    """Create a temporary test database."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    os.environ["DATABASE_URL"] = path
    yield path
    try:
        os.unlink(path)
    except:
        pass


@pytest.fixture
def client(test_db):
    """Create a test client with a fresh database."""
    # Import after environment is set
    from dashboard.app import app, init_db
    init_db()
    return TestClient(app)


def test_health_endpoint(client):
    """Health endpoint should return ok status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_index_empty(client):
    """Index page should render with no data."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Quality Gate Dashboard" in response.text


def test_trends_empty(client):
    """Trends page should render with no data."""
    response = client.get("/trends")
    assert response.status_code == 200


def test_api_series_empty(client):
    """API series should return empty dict when no data."""
    response = client.get("/api/series")
    assert response.status_code == 200
    assert response.json() == {}


def test_ingest_no_auth(client):
    """Ingest endpoint should reject requests without auth."""
    response = client.post("/ingest", json={})
    assert response.status_code == 401


def test_ingest_bad_token(client):
    """Ingest endpoint should reject bad tokens."""
    response = client.post(
        "/ingest",
        json={},
        headers={"Authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 403


def test_ingest_valid(client):
    """Ingest endpoint should accept valid data."""
    payload = {
        "repository": "test/repo",
        "pr_number": "123",
        "commit_sha": "abc123",
        "run_id": "456",
        "python": {
            "mutation": {
                "score": 85.5,
                "killed": 100,
                "survived": 17,
                "timeout": 0
            },
            "dependencies": {
                "critical": 0,
                "high": 1,
                "moderate": 2,
                "low": 5,
                "max_cvss": 7.5
            }
        }
    }
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    assert response.status_code == 200


def test_index_with_data(client, test_db):
    """Index should display ingested metrics."""
    # Ingest some data first
    payload = {
        "repository": "test/repo",
        "pr_number": "42",
        "commit_sha": "deadbeef",
        "run_id": "789",
        "python": {
            "mutation": {"score": 75.0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 1, "low": 0, "max_cvss": 5.0}
        }
    }
    client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    
    # Check index shows the data
    response = client.get("/")
    assert response.status_code == 200
    assert "test/repo" in response.text
    assert "75" in response.text  # mutation score


def test_api_series_with_data(client):
    """API series should return data grouped by ecosystem."""
    # Ingest test data
    payload = {
        "repository": "test/repo",
        "pr_number": "1",
        "commit_sha": "abc",
        "run_id": "1",
        "python": {
            "mutation": {"score": 80.0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 0, "low": 0, "max_cvss": 0.0}
        }
    }
    client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    
    response = client.get("/api/series")
    assert response.status_code == 200
    data = response.json()
    assert "python" in data
    assert len(data["python"]) > 0
    assert "avg_mutation" in data["python"][0]
