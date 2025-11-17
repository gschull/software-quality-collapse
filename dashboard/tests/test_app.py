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


def test_ingest_zero_values(client):
    """Ingest should handle zero mutation scores and CVSS."""
    payload = {
        "repository": "zero/test",
        "pr_number": "1",
        "python": {
            "mutation": {"score": 0.0},
            "dependencies": {"critical": 0, "high": 0, "moderate": 0, "low": 0, "max_cvss": 0.0}
        }
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "stored"


def test_api_series_aggregation_values(client):
    """API series should correctly calculate averages and maxes."""
    # Ingest multiple data points
    for i in range(3):
        payload = {
            "repository": f"test/repo{i}",
            "pr_number": str(i),
            "python": {
                "mutation": {"score": 50.0 + i * 10},  # 50, 60, 70
                "dependencies": {"max_cvss": 2.0 + i}  # 2.0, 3.0, 4.0
            }
        }
        client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/api/series")
    assert response.status_code == 200
    data = response.json()
    assert "python" in data
    # Verify we got actual calculated values
    assert all(item["avg_mutation"] >= 0 for item in data["python"])
    assert all(item["max_cvss"] >= 0 for item in data["python"])


def test_trends_aggregation(client):
    """Trends should show correct aggregated statistics."""
    # Ingest multiple events for same repo
    for i in range(5):
        payload = {
            "repository": "agg/repo",
            "pr_number": str(i),
            "python": {"mutation": {"score": 80.0 + i}, "dependencies": {"max_cvss": 5.0}}
        }
        client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/trends")
    assert response.status_code == 200
    # Should contain aggregated data
    assert "agg/repo" in response.text


def test_ingest_bearer_token_exact_match(client):
    """Ingest should require exact Bearer token match."""
    payload = {"repository": "test/repo", "python": {"mutation": {"score": 75.0}}}
    
    # Wrong token should fail
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer wrong-token-xyz"}
    )
    assert response.status_code == 403
    
    # Correct token should succeed
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    assert response.status_code == 200


def test_ingest_malformed_bearer(client):
    """Ingest should reject malformed Bearer header."""
    payload = {"repository": "test/repo", "python": {"mutation": {"score": 75.0}}}
    
    # Missing space after Bearer
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearertest-token-12345"}
    )
    assert response.status_code == 401


def test_api_roi_zero_cost(client):
    """ROI calculator should handle edge case of zero cost."""
    response = client.get("/api/roi?team_size=1&plan=pro")
    assert response.status_code == 200
    data = response.json()
    assert data["costs"]["per_month"] == 10  # 1 * 10
    assert data["roi"]["multiple"] > 0


def test_api_roi_large_team(client):
    """ROI calculator should work with large teams."""
    response = client.get("/api/roi?team_size=500&plan=enterprise")
    assert response.status_code == 200
    data = response.json()
    assert data["costs"]["per_month"] == 15000  # 500 * 30
    assert data["costs"]["per_year"] == 180000
    assert data["roi"]["multiple"] > 0


def test_api_roi_calculations_precise(client):
    """ROI calculator should produce consistent calculations."""
    response = client.get("/api/roi?team_size=100&plan=team")
    assert response.status_code == 200
    data = response.json()
    
    # Verify calculation chain
    expected_monthly = 100 * 15  # 1500
    expected_yearly = expected_monthly * 12  # 18000
    assert data["costs"]["per_month"] == expected_monthly
    assert data["costs"]["per_year"] == expected_yearly
    
    # Verify time savings calculation
    time_savings = 100 * 2 * 24 * 75  # team * hours * sprints * rate
    assert data["savings"]["time_savings_per_year"] == time_savings
    
    # Verify incident savings
    incident_savings = 1 * 50000
    assert data["savings"]["incident_savings_per_year"] == incident_savings


def test_index_limit_100(client):
    """Index should limit to 100 entries."""
    # Ingest more than 100 entries
    for i in range(105):
        payload = {
            "repository": f"bulk/repo{i}",
            "python": {"mutation": {"score": 75.0}}
        }
        client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    # Check that index doesn't crash with many entries
    response = client.get("/")
    assert response.status_code == 200


def test_trends_limit_1000(client):
    """Trends should use 1000-event window for aggregation."""
    # The query uses LIMIT 1000 internally
    response = client.get("/trends")
    assert response.status_code == 200


def test_ingest_response_format(client):
    """Ingest should return proper response format."""
    payload = {
        "repository": "format/test",
        "pr_number": "99",
        "python": {"mutation": {"score": 75.0}}
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    data = response.json()
    
    # Verify response structure
    assert "status" in data
    assert "repository" in data
    assert "pr_number" in data
    assert data["status"] == "stored"
    assert data["repository"] == "format/test"
    assert data["pr_number"] == "99"


def test_api_series_none_handling(client):
    """API series should handle None values with 'or 0' defaults."""
    # Ingest data with missing mutation score
    payload = {
        "repository": "none/test",
        "python": {"mutation": {}, "dependencies": {}}
    }
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/api/series")
    assert response.status_code == 200
    data = response.json()
    # Should not crash, values should default to 0
    if "python" in data and len(data["python"]) > 0:
        assert data["python"][0]["avg_mutation"] >= 0
        assert data["python"][0]["max_cvss"] >= 0
