import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import FastAPI, Request, Header, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

DB_PATH = os.environ.get("DATABASE_URL", "metrics.db")
INGEST_TOKEN = os.environ.get("INGEST_TOKEN", "change-me")

app = FastAPI(title="Quality Gate Dashboard", version="0.1.0")

BASE_DIR = os.path.dirname(__file__)
templates_env = Environment(
    loader=FileSystemLoader(os.path.join(BASE_DIR, "templates")),
    autoescape=select_autoescape(["html", "xml"]),
)


def get_conn():
    con = sqlite3.connect(DB_PATH)
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
        for eco_key in ("python", "java"):
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
