import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Header, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "change-me")

app = FastAPI(title="Quality Gate Dashboard", version="0.1.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Handle mutmut's mutants/ directory structure
if BASE_DIR.endswith("mutants"):
    BASE_DIR = os.path.dirname(BASE_DIR)
templates_env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_conn():
    # Read DB_PATH dynamically to support test fixture DATABASE_URL changes
    db_path = os.environ.get("DATABASE_URL", "metrics.db")
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    con = get_conn()
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repository TEXT NOT NULL,
            pr_number INTEGER,
            commit_sha TEXT,
            ecosystem TEXT,
            mutation_score REAL,
            dep_critical INTEGER,
            dep_high INTEGER,
            dep_moderate INTEGER,
            dep_low INTEGER,
            max_cvss REAL,
            run_id INTEGER,
            created_at TEXT NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            stripe_customer_id TEXT UNIQUE,
            stripe_subscription_id TEXT UNIQUE,
            plan TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            canceled_at TEXT,
            metadata TEXT
        )
        """
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_customers_email ON customers(email)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_customers_stripe_customer_id ON customers(stripe_customer_id)")
    con.commit()
    con.close()


@app.on_event("startup")
async def _startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index():
    con = get_conn()
    # Latest 100 entries
    rows = con.execute(
        "SELECT repository, pr_number, commit_sha, ecosystem, mutation_score, dep_critical, dep_high, dep_moderate, dep_low, max_cvss, run_id, created_at FROM events ORDER BY id DESC LIMIT 100"
    ).fetchall()
    con.close()
    tmpl = templates_env.get_template("index.html")
    return tmpl.render(rows=rows)


@app.get("/trends", response_class=HTMLResponse)
async def trends():
        con = get_conn()
        # Compute simple aggregates per repo and ecosystem on recent window
        rows = con.execute(
                """
                SELECT repository, ecosystem,
                             ROUND(AVG(mutation_score),2) AS avg_mutation,
                             ROUND(MAX(max_cvss),1) AS worst_cvss,
                             COUNT(*) AS samples
                FROM (
                    SELECT * FROM events ORDER BY id DESC LIMIT 1000
                ) e
                GROUP BY repository, ecosystem
                ORDER BY repository, ecosystem
                """
        ).fetchall()
        con.close()
        tmpl = templates_env.get_template("trends.html")
        return tmpl.render(rows=rows)


@app.get("/api/series")
async def api_series(limit: int = 1000):
        con = get_conn()
        # Aggregate by date for average mutation and max CVSS per ecosystem
        q = (
            "SELECT substr(created_at,1,10) AS day, ecosystem, "
            "ROUND(AVG(mutation_score),2) AS avg_mutation, "
            "ROUND(MAX(max_cvss),1) AS max_cvss "
            "FROM (SELECT * FROM events ORDER BY id DESC LIMIT ?) e "
            "GROUP BY day, ecosystem ORDER BY day"
        )
        rows = con.execute(q, (limit,)).fetchall()
        con.close()
        # Shape into {ecosystem: [{day, avg_mutation, max_cvss}, ...]}
        series = {}
        for r in rows:
            eco = r["ecosystem"]
            series.setdefault(eco, []).append({
                "day": r["day"],
                "avg_mutation": float(r["avg_mutation"] or 0),
                "max_cvss": float(r["max_cvss"] or 0)
            })
        return series


@app.post("/ingest")
async def ingest(request: Request, authorization: Optional[str] = Header(None)):
    # ELI5: This is a mailbox. The CI sends us a summary. We stamp it with time
    # and save it in a simple notebook (SQLite) so we can show trends later.
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = authorization.split(" ", 1)[1]
    if token != INGEST_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid token")

    data: Dict[str, Any] = await request.json()
    repo = data.get("repository")
    pr_number = data.get("pr_number")
    run_id = data.get("run_id")
    commit_sha = data.get("commit_sha")
    created_at = datetime.utcnow().isoformat()

    con = get_conn()
    try:
        for eco_key in ("python", "java", "node"):
            eco = data.get(eco_key)
            if not eco:
                continue
            mut = (eco.get("mutation") or {})
            deps = (eco.get("dependencies") or {})
            con.execute(
                """
                INSERT INTO events (repository, pr_number, commit_sha, ecosystem, mutation_score, dep_critical, dep_high, dep_moderate, dep_low, max_cvss, run_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo,
                    pr_number,
                    commit_sha,
                    eco_key,
                    float(mut.get("score") or 0),
                    int(deps.get("critical") or 0),
                    int(deps.get("high") or 0),
                    int(deps.get("moderate") or 0),
                    int(deps.get("low") or 0),
                    float(deps.get("max_cvss") or 0.0),
                    int(run_id or 0),
                    created_at,
                ),
            )
        con.commit()
    finally:
        con.close()
    return JSONResponse({"status": "stored", "repository": repo, "pr_number": pr_number})


@app.get("/billing")
async def billing_portal(email: str = Query(..., description="Customer email address")):
    """Redirect to Stripe billing portal for customer to manage subscription"""
    con = get_conn()
    customer = con.execute("SELECT * FROM customers WHERE email = ?", (email,)).fetchone()
    con.close()
    
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found. Please contact support.")
    
    # For MVP, return simple page with manual instructions
    # Later: integrate stripe.billing_portal.Session.create()
    html = f"""
    <html>
    <head><title>Billing Portal</title></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: 50px auto; padding: 20px;">
        <h1>Billing Portal (MVP)</h1>
        <p><strong>Email:</strong> {customer['email']}</p>
        <p><strong>Plan:</strong> {customer['plan']}</p>
        <p><strong>Status:</strong> {customer['status']}</p>
        <p><strong>Created:</strong> {customer['created_at']}</p>
        <hr>
        <h3>To Update Payment Method or Cancel:</h3>
        <p>Please email <a href="mailto:billing@quality-gate.dev">billing@quality-gate.dev</a> with your request.</p>
        <p><small>Self-service billing portal coming soon (Stripe integration in progress).</small></p>
    </body>
    </html>
    """
    return HTMLResponse(html)


@app.get("/api/pricing")
async def get_pricing():
    """Return pricing tiers for landing page"""
    return {
        "pro": {
            "price_per_dev": 10,
            "min_seats": 5,
            "billing": "monthly",
            "features": [
                "Hosted dashboard",
                "90-day trend history",
                "Slack/Discord webhooks",
                "Email support (48h SLA)",
                "Private repos"
            ]
        },
        "team": {
            "price_per_dev": 15,
            "min_seats": 20,
            "billing": "monthly",
            "features": [
                "Everything in Pro",
                "Org-wide policy management",
                "SAML SSO",
                "Audit logs",
                "Priority support (24h SLA)",
                "1-year history"
            ]
        },
        "enterprise": {
            "price_per_dev": 30,
            "min_seats": 200,
            "billing": "custom",
            "features": [
                "Everything in Team",
                "On-premises deployment",
                "Compliance reports (SOC 2, HIPAA)",
                "White-label dashboard",
                "Dedicated CSM",
                "Unlimited history"
            ]
        }
    }


@app.get("/api/roi")
async def calculate_roi(
    team_size: int = Query(25, ge=1, le=10000),
    plan: str = Query("pro", regex="^(pro|team|enterprise)$")
):
    """Calculate ROI for pricing calculator on landing page"""
    prices = {"pro": 10, "team": 15, "enterprise": 30}
    cost_per_month = team_size * prices[plan]
    
    # Research-backed assumptions (from blog post analysis)
    hours_saved_per_dev_per_sprint = 2
    sprints_per_year = 24
    hourly_rate = 75
    incidents_prevented_per_year = 1
    incident_cost = 50000
    
    time_savings_per_year = team_size * hours_saved_per_dev_per_sprint * sprints_per_year * hourly_rate
    incident_savings_per_year = incidents_prevented_per_year * incident_cost
    total_value_per_year = time_savings_per_year + incident_savings_per_year
    
    cost_per_year = cost_per_month * 12
    roi_multiple = round(total_value_per_year / cost_per_year, 1) if cost_per_year > 0 else 0
    payback_period_days = round(365 / roi_multiple, 0) if roi_multiple > 0 else 365
    
    return {
        "inputs": {
            "team_size": team_size,
            "plan": plan
        },
        "costs": {
            "per_month": cost_per_month,
            "per_year": cost_per_year
        },
        "savings": {
            "time_savings_per_year": time_savings_per_year,
            "incident_savings_per_year": incident_savings_per_year,
            "total_value_per_year": total_value_per_year
        },
        "roi": {
            "multiple": roi_multiple,
            "payback_period_days": int(payback_period_days),
            "annual_return_percentage": round((roi_multiple - 1) * 100, 0)
        }
    }


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events (subscription lifecycle)"""
    # For MVP, just log events; full Stripe integration in STRIPE_SETUP.md
    payload = await request.json()
    event_type = payload.get("type")
    
    # In production: verify webhook signature, handle events
    # See docs/STRIPE_SETUP.md for full implementation
    
    return {"received": True, "event_type": event_type}
