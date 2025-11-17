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
    """Provide a temporary database for tests."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    # Ensure the file is deleted before we start (clean slate)
    if os.path.exists(path):
        os.unlink(path)
    # Use absolute path to prevent path resolution issues
    path = os.path.abspath(path)
    os.environ["DATABASE_URL"] = path
    yield path
    # Clean up
    try:
        if os.path.exists(path):
            os.unlink(path)
    except:
        pass
    # Clean up environment to avoid pollution
    if "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


@pytest.fixture
def client(test_db):
    """Provide a test client with a clean database."""
    # Import after environment is set up
    from app import app, init_db
    # Ensure fresh initialization
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
    assert "day" in data["python"][0]
    assert "max_cvss" in data["python"][0]


def test_api_series_with_limit(client):
    """API series should respect limit parameter."""
    # Ingest data
    payload = {
        "repository": "test/repo",
        "pr_number": "1",
        "commit_sha": "abc",
        "run_id": "1",
        "python": {"mutation": {"score": 85.0}, "dependencies": {"max_cvss": 3.0}}
    }
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/api/series?limit=10")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)


def test_ingest_multiple_ecosystems(client):
    """Ingest should handle multiple ecosystems in one payload."""
    payload = {
        "repository": "multi/lang",
        "pr_number": "99",
        "commit_sha": "multi123",
        "run_id": "999",
        "python": {
            "mutation": {"score": 70.0},
            "dependencies": {"critical": 1, "high": 2, "moderate": 3, "low": 4, "max_cvss": 9.0}
        },
        "java": {
            "mutation": {"score": 60.0},
            "dependencies": {"critical": 0, "high": 1, "moderate": 0, "low": 0, "max_cvss": 6.5}
        },
        "node": {
            "mutation": {"score": 50.0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 5, "low": 10, "max_cvss": 4.2}
        }
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    data = response.json()
    assert data["repository"] == "multi/lang"
    assert data["pr_number"] == "99"


def test_trends_with_data(client):
    """Trends page should display aggregated data."""
    # Ingest test data
    payload = {
        "repository": "test/trends",
        "pr_number": "10",
        "commit_sha": "trends123",
        "run_id": "100",
        "python": {
            "mutation": {"score": 65.0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 1, "low": 2, "max_cvss": 5.5}
        }
    }
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/trends")
    assert response.status_code == 200
    assert "test/trends" in response.text


def test_api_pricing(client):
    """Pricing API should return all tier information."""
    response = client.get("/api/pricing")
    assert response.status_code == 200
    data = response.json()
    assert "pro" in data
    assert "team" in data
    assert "enterprise" in data
    assert data["pro"]["price_per_dev"] == 10
    assert data["team"]["price_per_dev"] == 15
    assert data["enterprise"]["price_per_dev"] == 30
    assert "features" in data["pro"]


def test_api_roi_default(client):
    """ROI calculator should work with default parameters."""
    response = client.get("/api/roi")
    assert response.status_code == 200
    data = response.json()
    assert "inputs" in data
    assert "costs" in data
    assert "savings" in data
    assert "roi" in data
    assert data["inputs"]["team_size"] == 25
    assert data["inputs"]["plan"] == "pro"
    assert data["roi"]["multiple"] > 0


def test_api_roi_custom_params(client):
    """ROI calculator should accept custom parameters."""
    response = client.get("/api/roi?team_size=50&plan=team")
    assert response.status_code == 200
    data = response.json()
    assert data["inputs"]["team_size"] == 50
    assert data["inputs"]["plan"] == "team"
    assert data["costs"]["per_month"] == 750  # 50 * 15


def test_webhook_stripe(client):
    """Stripe webhook should accept events."""
    payload = {"type": "customer.subscription.created", "data": {}}
    response = client.post("/webhook/stripe", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["received"] is True
    assert data["event_type"] == "customer.subscription.created"


def test_billing_portal_not_found(client):
    """Billing portal should return 404 for unknown customer."""
    response = client.get("/billing?email=unknown@example.com")
    assert response.status_code == 404


def test_billing_portal_with_customer(client, test_db):
    """Billing portal should display customer info."""
    # Insert a test customer
    from app import get_conn
    con = get_conn()
    con.execute(
        "INSERT INTO customers (email, plan, status, created_at) VALUES (?, ?, ?, ?)",
        ("test@example.com", "pro", "active", "2025-01-01T00:00:00")
    )
    con.commit()
    con.close()
    
    response = client.get("/billing?email=test@example.com")
    assert response.status_code == 200
    assert "test@example.com" in response.text
    assert "pro" in response.text
    assert "active" in response.text


def test_ingest_missing_fields(client):
    """Ingest should handle payloads with missing optional fields."""
    payload = {
        "repository": "minimal/repo",
        "python": {"mutation": {"score": 100.0}}
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200


def test_ingest_empty_ecosystem(client):
    """Ingest should skip ecosystems with no data."""
    payload = {
        "repository": "skip/test",
        "pr_number": "1",
        "python": {"mutation": {"score": 50.0}},
        "java": None
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
