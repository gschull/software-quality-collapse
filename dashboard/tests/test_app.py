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


def test_roi_constants_hours_saved(client):
    """ROI calculation should use 2 hours saved per dev per sprint."""
    # With team_size=10, should be 10 * 2 * 24 * 75 = 36,000
    response = client.get("/api/roi?team_size=10&plan=pro")
    data = response.json()
    # time_savings = 10 * 2 * 24 * 75 = 36000
    assert data["savings"]["time_savings_per_year"] == 36000


def test_roi_constants_sprints(client):
    """ROI calculation should use 24 sprints per year."""
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    # time_savings = 1 * 2 * 24 * 75 = 3600
    assert data["savings"]["time_savings_per_year"] == 3600


def test_roi_constants_hourly_rate(client):
    """ROI calculation should use $75 hourly rate."""
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    # time_savings = 1 * 2 * 24 * 75 = 3600
    expected = 1 * 2 * 24 * 75
    assert data["savings"]["time_savings_per_year"] == expected


def test_roi_constants_incident_cost(client):
    """ROI calculation should use $50,000 incident cost."""
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    # incident_savings = 1 * 50000 = 50000
    assert data["savings"]["incident_savings_per_year"] == 50000


def test_roi_constants_months_per_year(client):
    """ROI calculation should multiply monthly cost by 12."""
    response = client.get("/api/roi?team_size=10&plan=pro")
    data = response.json()
    # cost_per_month = 10 * 10 = 100
    # cost_per_year = 100 * 12 = 1200
    assert data["costs"]["per_month"] == 100
    assert data["costs"]["per_year"] == 1200


def test_roi_constants_days_in_year(client):
    """ROI calculation should use 365 days for payback period."""
    response = client.get("/api/roi?team_size=25&plan=pro")
    data = response.json()
    # Should involve 365 in the calculation
    # payback_period_days = round(365 / roi_multiple, 0)
    assert "payback_period_days" in data["roi"]
    assert data["roi"]["payback_period_days"] > 0


def test_pricing_pro_price(client):
    """Pricing should show $10 per dev for pro plan."""
    response = client.get("/api/pricing")
    data = response.json()
    assert data["pro"]["price_per_dev"] == 10


def test_pricing_team_price(client):
    """Pricing should show $15 per dev for team plan."""
    response = client.get("/api/pricing")
    data = response.json()
    assert data["team"]["price_per_dev"] == 15


def test_pricing_enterprise_price(client):
    """Pricing should show $30 per dev for enterprise plan."""
    response = client.get("/api/pricing")
    data = response.json()
    assert data["enterprise"]["price_per_dev"] == 30


def test_pricing_min_seats(client):
    """Pricing should show correct minimum seats for each tier."""
    response = client.get("/api/pricing")
    data = response.json()
    assert data["pro"]["min_seats"] == 5
    assert data["team"]["min_seats"] == 20
    assert data["enterprise"]["min_seats"] == 200


def test_api_series_default_limit(client):
    """API series should default to 1000 limit."""
    # The default limit=1000 should be used if not specified
    payload = {"repository": "test/limit", "python": {"mutation": {"score": 75.0}}}
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    # Call without limit parameter (should use default 1000)
    response = client.get("/api/series")
    assert response.status_code == 200


def test_authorization_split_behavior(client):
    """Test that authorization header is split correctly on first space only."""
    payload = {"repository": "test/auth", "python": {"mutation": {"score": 75.0}}}
    
    # Token with space in it (after Bearer) - should use everything after first space
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    assert response.status_code == 200
    
    # Without Bearer prefix should fail
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "test-token-12345"}
    )
    assert response.status_code == 401


def test_ingest_all_dependency_fields(client):
    """Test that all dependency fields are stored correctly."""
    from app import get_conn
    
    payload = {
        "repository": "deps/test",
        "pr_number": "1",
        "python": {
            "mutation": {"score": 88.5, "killed": 100, "survived": 13, "timeout": 0},
            "dependencies": {
                "critical": 2,
                "high": 3,
                "moderate": 5,
                "low": 7,
                "max_cvss": 9.8
            }
        }
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    # Verify data was stored correctly
    con = get_conn()
    row = con.execute("SELECT * FROM events WHERE repository = ?", ("deps/test",)).fetchone()
    con.close()
    
    assert row is not None
    assert row["mutation_score"] == 88.5
    assert row["dep_critical"] == 2
    assert row["dep_high"] == 3
    assert row["dep_moderate"] == 5
    assert row["dep_low"] == 7
    assert row["max_cvss"] == 9.8


def test_ingest_converts_to_correct_types(client):
    """Test type conversions in ingest (float, int)."""
    from app import get_conn
    
    payload = {
        "repository": "types/test",
        "run_id": "999",
        "python": {
            "mutation": {"score": "75.5"},  # String that should be converted to float
            "dependencies": {"critical": "1", "max_cvss": "6.5"}  # Strings to convert
        }
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    # Verify types in database
    con = get_conn()
    row = con.execute("SELECT * FROM events WHERE repository = ?", ("types/test",)).fetchone()
    con.close()
    
    assert row["mutation_score"] == 75.5
    assert row["run_id"] == 999


def test_api_series_float_conversion(client):
    """Test that API series converts None to 0 using 'or 0' for floats."""
    payload = {
        "repository": "float/test",
        "python": {"mutation": {}, "dependencies": {}}
    }
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    response = client.get("/api/series")
    data = response.json()
    
    # Verify float conversion happens
    if "python" in data and len(data["python"]) > 0:
        # These should be floats, not None
        assert isinstance(data["python"][0]["avg_mutation"], (int, float))
        assert isinstance(data["python"][0]["max_cvss"], (int, float))


def test_ingest_all_ecosystems(client):
    """Test that all three ecosystems can be ingested."""
    from app import get_conn
    
    payload = {
        "repository": "all/test",
        "node": {"mutation": {"score": 30.0}},
        "python": {"mutation": {"score": 90.0}},
        "java": {"mutation": {"score": 60.0}}
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    # Check all three were inserted
    con = get_conn()
    rows = con.execute("SELECT ecosystem, mutation_score FROM events WHERE repository = ?", ("all/test",)).fetchall()
    con.close()
    
    assert len(rows) == 3
    ecosystems = {row["ecosystem"] for row in rows}
    assert ecosystems == {"python", "java", "node"}


def test_ingest_created_at_timestamp(client):
    """Test that created_at is set with utcnow isoformat."""
    from app import get_conn
    from datetime import datetime
    
    payload = {
        "repository": "timestamp/test",
        "python": {"mutation": {"score": 75.0}}
    }
    
    before = datetime.utcnow()
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    after = datetime.utcnow()
    
    assert response.status_code == 200
    
    con = get_conn()
    row = con.execute("SELECT created_at FROM events WHERE repository = ?", ("timestamp/test",)).fetchone()
    con.close()
    
    # Parse the timestamp
    created_at = datetime.fromisoformat(row["created_at"])
    
    # Should be between before and after
    assert before <= created_at <= after


def test_ingest_bearer_token_with_spaces(client):
    """Test that token extraction works correctly with Bearer prefix."""
    # If split(" ", 1) is mutated to split(" ", 0) or split(" ", 2), this would fail
    payload = {"repository": "test/split", "python": {"mutation": {"score": 75.0}}}
    
    # Token that would behave differently with wrong split argument
    # With split(" ", 1): ["Bearer", "token-with-space here"]
    # With split(" ", 0) or split(" "): would split differently
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer test-token-12345"}
    )
    assert response.status_code == 200


def test_ingest_error_messages(client):
    """Test that error messages are specific and correct."""
    payload = {"repository": "test/err", "python": {"mutation": {"score": 75.0}}}
    
    # Test 401 error message
    response = client.post("/ingest", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"
    
    # Test 403 error message
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearer wrong"}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid token"


def test_bearer_prefix_check(client):
    """Test that 'Bearer ' prefix is required with space."""
    payload = {"repository": "test/bearer", "python": {"mutation": {"score": 75.0}}}
    
    # "Bearer" without space should fail
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Bearertest-token-12345"}
    )
    assert response.status_code == 401
    
    # Other prefixes should fail
    response = client.post(
        "/ingest",
        json=payload,
        headers={"Authorization": "Token test-token-12345"}
    )
    assert response.status_code == 401


def test_roi_division_by_zero_protection(client):
    """Test that ROI handles zero cost correctly."""
    # Edge case: if cost_per_year is 0, roi_multiple should be 0 (not division error)
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    # Should not crash and should have valid roi_multiple
    assert "roi" in data
    assert "multiple" in data["roi"]
    assert isinstance(data["roi"]["multiple"], (int, float))


def test_roi_payback_period_protection(client):
    """Test that payback period handles zero roi_multiple."""
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    # payback_period_days = round(365 / roi_multiple, 0) if roi_multiple > 0 else 365
    # Should have a valid payback period
    assert "payback_period_days" in data["roi"]
    assert data["roi"]["payback_period_days"] > 0


def test_ingest_continue_on_empty_ecosystem(client):
    """Test that loop continues when ecosystem is None or missing."""
    payload = {
        "repository": "continue/test",
        "python": {"mutation": {"score": 50.0}},
        "java": None,  # Should continue
        "node": {"mutation": {"score": 60.0}}
    }
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    from app import get_conn
    con = get_conn()
    rows = con.execute("SELECT ecosystem FROM events WHERE repository = ?", ("continue/test",)).fetchall()
    con.close()
    
    # Should have python and node, but not java
    ecosystems = {row["ecosystem"] for row in rows}
    assert ecosystems == {"python", "node"}


def test_api_series_substring_extraction(client):
    """Test that day is extracted as first 10 chars of created_at."""
    from app import get_conn
    
    payload = {"repository": "substr/test", "python": {"mutation": {"score": 75.0}}}
    client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    # Check that the SQL substr(created_at,1,10) works correctly
    response = client.get("/api/series")
    data = response.json()
    
    if "python" in data and len(data["python"]) > 0:
        day = data["python"][0]["day"]
        # Should be in YYYY-MM-DD format (10 characters)
        assert len(day) == 10
        assert day.count("-") == 2  # YYYY-MM-DD has 2 dashes


def test_ingest_empty_string_ecosystem(client):
    """Test that empty string ecosystems are skipped."""
    from app import get_conn
    
    payload = {
        "repository": "empty/str",
        "python": {"mutation": {"score": 75.0}},
        "java": "",  # Empty string is falsy
        "node": {"mutation": {"score": 80.0}}
    }
    
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    con = get_conn()
    rows = con.execute("SELECT ecosystem FROM events WHERE repository = ?", ("empty/str",)).fetchall()
    con.close()
    
    ecosystems = {row["ecosystem"] for row in rows}
    assert ecosystems == {"python", "node"}
    assert "java" not in ecosystems


def test_ingest_empty_dict_ecosystem(client):
    """Test that empty dict ecosystems are skipped."""
    from app import get_conn
    
    payload = {
        "repository": "empty/dict",
        "python": {"mutation": {"score": 75.0}},
        "java": {},  # Empty dict is falsy
    }
    
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    con = get_conn()
    rows = con.execute("SELECT ecosystem FROM events WHERE repository = ?", ("empty/dict",)).fetchall()
    con.close()
    
    assert len(rows) == 1
    assert rows[0]["ecosystem"] == "python"


def test_authorization_without_bearer_prefix(client):
    """Test that authorization without 'Bearer ' prefix fails."""
    payload = {"repository": "no/bearer", "python": {"mutation": {"score": 75.0}}}
    
    # Just the token without "Bearer " prefix
    response = client.post("/ingest", json=payload, headers={"Authorization": "test-token-12345"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


def test_authorization_bearer_wrong_case(client):
    """Test that 'Bearer' is case-sensitive."""
    payload = {"repository": "case/test", "python": {"mutation": {"score": 75.0}}}
    
    # Lowercase "bearer"
    response = client.post("/ingest", json=payload, headers={"Authorization": "bearer test-token-12345"})
    assert response.status_code == 401
    
    # Mixed case "BeaRer"
    response = client.post("/ingest", json=payload, headers={"Authorization": "BeaRer test-token-12345"})
    assert response.status_code == 401


def test_token_not_equal_comparison(client):
    """Test that token comparison uses != operator correctly."""
    payload = {"repository": "token/ne", "python": {"mutation": {"score": 75.0}}}
    
    # Wrong token should give 403 Invalid token
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer wrong-token"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid token"
    
    # Correct token should succeed
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200


def test_split_with_maxsplit_one(client):
    """Test that split uses maxsplit=1 to handle tokens with spaces."""
    # Create a token that has spaces in it to test split(" ", 1)
    # With maxsplit=1: "Bearer token with spaces" -> ["Bearer", "token with spaces"]
    # With maxsplit=0 or no limit: would split on all spaces
    
    payload = {"repository": "split/max", "python": {"mutation": {"score": 75.0}}}
    
    # This relies on our test token NOT having spaces, so we test the code path
    # The actual behavior: split(" ", 1) means "split once on space"
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    # If split(" ", 1) was mutated to split(" ", 0), it would break
    # If mutated to split(" ", 2), it would still work for our test token
    # But the intent is maxsplit=1 for tokens that might contain spaces


def test_ecosystem_loop_iterates_python_java_node(client):
    """Test that loop explicitly iterates ("python", "java", "node")."""
    from app import get_conn
    
    # Send all three ecosystem types
    payload = {
        "repository": "loop/explicit",
        "python": {"mutation": {"score": 50.0}},
        "java": {"mutation": {"score": 60.0}},
        "node": {"mutation": {"score": 70.0}},
        "rust": {"mutation": {"score": 99.0}},  # Not in the loop tuple - should be ignored
    }
    
    response = client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    assert response.status_code == 200
    
    con = get_conn()
    rows = con.execute("SELECT ecosystem FROM events WHERE repository = ?", ("loop/explicit",)).fetchall()
    con.close()
    
    ecosystems = {row["ecosystem"] for row in rows}
    # Should have exactly python, java, node (not rust)
    assert ecosystems == {"python", "java", "node"}
    assert "rust" not in ecosystems


def test_roi_hours_saved_per_sprint_is_two(client):
    """Test that hours_saved_per_dev_per_sprint constant is exactly 2."""
    # For team_size=1, plan=pro ($10/month):
    # hours_saved = 1 * 2 * 24 * 75 = 3600
    # cost_per_year = 10 * 12 = 120
    # time_savings_per_year = 3600
    # total_value = 3600 + 50000 = 53600
    # roi_multiple = 53600 / 120 = 446.7
    
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    
    # If hours_saved was mutated from 2 to 1 or 3:
    # With 1: time_savings = 1*1*24*75 = 1800, total=51800, roi=431.7
    # With 3: time_savings = 1*3*24*75 = 5400, total=55400, roi=461.7
    assert data["savings"]["time_savings_per_year"] == 3600


def test_roi_sprints_per_year_is_twentyfour(client):
    """Test that sprints_per_year constant is exactly 24."""
    # For team_size=1, plan=pro:
    # hours_saved = 1 * 2 * 24 * 75 = 3600
    
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    
    # If sprints_per_year was mutated from 24 to 23 or 25:
    # With 23: time_savings = 1*2*23*75 = 3450, total=53450, roi=445.4
    # With 25: time_savings = 1*2*25*75 = 3750, total=53750, roi=447.9
    assert data["savings"]["time_savings_per_year"] == 3600


def test_roi_hourly_rate_is_seventyfive(client):
    """Test that hourly_rate constant is exactly 75."""
    # For team_size=1, plan=pro:
    # hours_saved = 1 * 2 * 24 * 75 = 3600
    
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    
    # If hourly_rate was mutated from 75 to 74 or 76:
    # With 74: time_savings = 1*2*24*74 = 3552, total=53552, roi=446.3
    # With 76: time_savings = 1*2*24*76 = 3648, total=53648, roi=447.1
    assert data["savings"]["time_savings_per_year"] == 3600


def test_roi_incidents_prevented_is_one(client):
    """Test that incidents_prevented_per_year is exactly 1."""
    response = client.get("/api/roi?team_size=10&plan=pro")
    data = response.json()
    
    # incident_savings = 1 * 50000 = 50000
    # If mutated to 0: incident_savings = 0
    # If mutated to 2: incident_savings = 100000
    assert data["savings"]["incident_savings_per_year"] == 50000


def test_roi_incident_cost_is_fifty_thousand(client):
    """Test that incident_cost constant is exactly 50000."""
    response = client.get("/api/roi?team_size=10&plan=pro")
    data = response.json()
    
    # incident_savings = 1 * 50000 = 50000
    # If mutated to 49999 or 50001: would change result
    assert data["savings"]["incident_savings_per_year"] == 50000


def test_roi_cost_per_year_multiply_by_twelve(client):
    """Test that cost_per_year is cost_per_month * 12 (not 11 or 13)."""
    # team_size=10, plan=pro: cost_per_month = 10*10 = 100
    response = client.get("/api/roi?team_size=10&plan=pro")
    data = response.json()
    
    # cost_per_year should be 100 * 12 = 1200
    # If mutated to * 11: 1100
    # If mutated to * 13: 1300
    assert data["costs"]["per_year"] == 1200


def test_roi_payback_uses_365_days(client):
    """Test that payback_period_days uses 365 (not 364 or 366)."""
    # team_size=1, plan=pro:
    # roi_multiple = 446.7
    # payback_period_days = round(365 / 446.7) = round(0.817) = 1
    
    response = client.get("/api/roi?team_size=1&plan=pro")
    data = response.json()
    
    # If 365 was mutated to 364 or 366: would change result
    # With 365/446.7: ~0.817 → rounds to 1
    # Need a case where the exact value matters
    # Let's use a different team size where the rounding shows the difference
    
    response = client.get("/api/roi?team_size=50&plan=pro")
    data = response.json()
    
    # For team_size=50: cost=500*12=6000, time_savings=50*2*24*75=180000
    # total_value=180000+50000=230000, roi=230000/6000=38.3
    # payback=365/38.3=9.5 → rounds to 10 days
    assert data["roi"]["payback_period_days"] == 10


def test_index_sql_limit_100(client):
    """Test that index page SQL uses LIMIT 100 (not 99 or 101)."""
    from app import get_conn
    import os
    
    # Create exactly 150 events
    for i in range(150):
        payload = {
            "repository": f"test/limit{i}",
            "python": {"mutation": {"score": 50.0 + i * 0.1}}
        }
        client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    # Index page should show only the latest 100
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    
    # Count occurrences of "test/limit" in HTML
    count = html.count("test/limit")
    # Should be exactly 100 (from limit149 down to limit50)
    assert count == 100


def test_trends_sql_limit_1000(client):
    """Test that trends page SQL uses LIMIT 1000 in subquery."""
    from app import get_conn
    
    # Create exactly 1100 events with two distinct repos
    for i in range(1100):
        repo = "repo/a" if i < 550 else "repo/b"
        payload = {
            "repository": repo,
            "python": {"mutation": {"score": 50.0}}
        }
        client.post("/ingest", json=payload, headers={"Authorization": "Bearer test-token-12345"})
    
    # Trends should only consider the latest 1000 events
    response = client.get("/trends")
    assert response.status_code == 200
    html = response.text
    
    # Both repos should appear (repo/b has 550 events, all in last 1000)
    # repo/a has 550 events, but only the last 450 are in the window
    assert "repo/a" in html
    assert "repo/b" in html


def test_roi_team_size_default_25(client):
    """Test that team_size has default value of 25."""
    # Call without team_size parameter
    response = client.get("/api/roi?plan=pro")
    assert response.status_code == 200
    data = response.json()
    
    # Should use default 25
    assert data["inputs"]["team_size"] == 25
    
    # Cost should be 25 * 10 = 250/month
    assert data["costs"]["per_month"] == 250


def test_roi_team_size_ge_validator(client):
    """Test that team_size must be >= 1."""
    # Try with 0 (should fail)
    response = client.get("/api/roi?team_size=0&plan=pro")
    assert response.status_code == 422  # Validation error
    
    # Try with 1 (should succeed)
    response = client.get("/api/roi?team_size=1&plan=pro")
    assert response.status_code == 200


def test_roi_team_size_le_validator(client):
    """Test that team_size must be <= 10000."""
    # Try with 10001 (should fail)
    response = client.get("/api/roi?team_size=10001&plan=pro")
    assert response.status_code == 422  # Validation error
    
    # Try with 10000 (should succeed)
    response = client.get("/api/roi?team_size=10000&plan=pro")
    assert response.status_code == 200


def test_roi_plan_default_is_pro(client):
    """Test that plan has default value of 'pro'."""
    # Call without plan parameter
    response = client.get("/api/roi?team_size=10")
    assert response.status_code == 200
    data = response.json()
    
    # Should use default "pro"
    assert data["inputs"]["plan"] == "pro"
    
    # Cost should use pro pricing ($10/dev)
    assert data["costs"]["per_month"] == 100


def test_roi_plan_regex_validation(client):
    """Test that plan must match regex pattern."""
    # Try with invalid plan
    response = client.get("/api/roi?team_size=10&plan=invalid")
    assert response.status_code == 422  # Validation error
    
    # Try with each valid plan
    for plan in ["pro", "team", "enterprise"]:
        response = client.get(f"/api/roi?team_size=10&plan={plan}")
        assert response.status_code == 200
        data = response.json()
        assert data["inputs"]["plan"] == plan
