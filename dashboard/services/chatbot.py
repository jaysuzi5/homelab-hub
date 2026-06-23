import json
import re
from openai import OpenAI
from django.db import connection
from config.utils import get_config
from dashboard.services.status_overview import collect_status_overview
from dashboard.services.k8s import collect_k8s_metrics_detailed

_BASE_URL = "https://api.groq.com/openai/v1"
_MODEL = "llama-3.3-70b-versatile"
_MAX_TOOL_ROUNDS = 6
_SQL_ROW_LIMIT = 100

_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|grant|revoke|create|comment|copy|"
    r"vacuum|reindex|merge|call|do|set|begin|commit|rollback)\b",
    re.IGNORECASE,
)

_SYSTEM_PROMPT = """You are the Homelab Hub system health assistant. You help the owner \
understand the current state of their self-hosted infrastructure.

You have tools to:
- get an aggregated system status summary (issues + per-subsystem rollup),
- inspect the Kubernetes cluster (nodes, pod counts, problem pods),
- query the application PostgreSQL database (read-only) — list tables, describe a \
table, and run SELECT queries.

Much of the dashboard data lives in PostgreSQL (monitored hosts and ping results, \
portfolio, books, guitar sessions, claude usage snapshots, config key/values, etc.). \
Use list_tables / describe_table to discover the schema before writing SQL. Keep SQL \
to simple read-only SELECTs.

For CURRENT health (what is up/down/failing right now), prefer the system_status and \
k8s_overview tools — they already compute the live state. Database tables often store \
HISTORY (e.g. every ping result over time), so a raw COUNT over them is not "now"; to \
read current values from SQL you must take the latest row per entity. Use SQL mainly for \
historical trends, totals, and details not covered by the status tools.

Be concise and factual. Lead with the answer. If something is wrong, say what and where. \
If you lack data, say so rather than guessing."""


def _client():
    key = get_config("GROQ_API_KEY", "")
    if not key:
        return None
    return OpenAI(api_key=key, base_url=_BASE_URL)


# ---------------- Tools ----------------

def _tool_system_status(args):
    return collect_status_overview()


def _tool_k8s_overview(args):
    d = collect_k8s_metrics_detailed()
    pods = d.get("pod_details") or []
    problems = [p for p in pods if p.get("status") != "Running" or (p.get("restarts") or 0) > 0]
    return {
        "pods_status": d.get("pods_status"),
        "total_pods": d.get("total_pods"),
        "cluster_cpu_percent": d.get("cluster_cpu_percent"),
        "cluster_mem_percent": d.get("cluster_mem_percent"),
        "cluster_alerts": d.get("cluster_alerts"),
        "nodes": [{"name": n.get("name"), "ready": n.get("ready"),
                   "cpu_percent": n.get("cpu_percent"), "mem_percent": n.get("mem_percent")}
                  for n in (d.get("nodes_info") or [])],
        "problem_pods": problems[:40],
    }


def _tool_list_tables(args):
    with connection.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        return {"tables": [r[0] for r in cur.fetchall()]}


def _tool_describe_table(args):
    table = (args or {}).get("table", "")
    if not re.fullmatch(r"[A-Za-z0-9_]+", table or ""):
        return {"error": "Invalid table name."}
    with connection.cursor() as cur:
        cur.execute(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
            [table],
        )
        cols = [{"column": r[0], "type": r[1]} for r in cur.fetchall()]
    if not cols:
        return {"error": f"Table '{table}' not found."}
    return {"table": table, "columns": cols}


def _tool_run_sql(args):
    query = ((args or {}).get("query") or "").strip().rstrip(";")
    if not query:
        return {"error": "Empty query."}
    if not re.match(r"^\s*(select|with)\b", query, re.IGNORECASE):
        return {"error": "Only SELECT queries are allowed."}
    if ";" in query:
        return {"error": "Multiple statements are not allowed."}
    if _FORBIDDEN_SQL.search(query):
        return {"error": "Query contains a disallowed keyword. Read-only SELECT only."}

    if not re.search(r"\blimit\b", query, re.IGNORECASE):
        query = f"{query} LIMIT {_SQL_ROW_LIMIT}"

    try:
        with connection.cursor() as cur:
            cur.execute("SET LOCAL statement_timeout = 8000")
            cur.execute(query)
            columns = [c[0] for c in cur.description]
            rows = cur.fetchmany(_SQL_ROW_LIMIT)
        data = [dict(zip(columns, row)) for row in rows]
        return {"columns": columns, "row_count": len(data), "rows": data}
    except Exception as e:
        return {"error": str(e)}


_TOOLS = {
    "system_status": _tool_system_status,
    "k8s_overview": _tool_k8s_overview,
    "list_tables": _tool_list_tables,
    "describe_table": _tool_describe_table,
    "run_sql": _tool_run_sql,
}

_TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "system_status",
            "description": "Aggregated health summary: overall state, list of active issues, and per-subsystem rollup (Kubernetes, Synology NAS, network, monitored hosts, backups, AWS spending, Claude Code usage).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "k8s_overview",
            "description": "Kubernetes cluster state: pod phase counts, node readiness and CPU/memory, cluster alerts, and a list of problem pods (not Running or with restarts).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all tables in the application PostgreSQL database (public schema).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "describe_table",
            "description": "Return the column names and types for a given database table.",
            "parameters": {
                "type": "object",
                "properties": {"table": {"type": "string", "description": "Table name"}},
                "required": ["table"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_sql",
            "description": "Run a single read-only SELECT query against the PostgreSQL database and return rows. No INSERT/UPDATE/DELETE/DDL. Results are capped at 100 rows.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "A single SELECT statement"}},
                "required": ["query"],
            },
        },
    },
]


def _serialize(obj):
    return json.dumps(obj, default=str)


def answer_question(history):
    """history: list of {role, content}. Returns {'reply': str, 'error': str|None}."""
    client = _client()
    if client is None:
        return {"reply": "", "error": "Chatbot is not configured (missing GROQ_API_KEY)."}

    messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
    for turn in history[-12:]:
        role = turn.get("role")
        content = turn.get("content", "")
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})

    try:
        for _ in range(_MAX_TOOL_ROUNDS):
            resp = client.chat.completions.create(
                model=_MODEL,
                messages=messages,
                tools=_TOOL_SPECS,
                tool_choice="auto",
                temperature=0.2,
                max_tokens=900,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                return {"reply": msg.content or "", "error": None}

            messages.append({
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })

            for tc in msg.tool_calls:
                fn = _TOOLS.get(tc.function.name)
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except Exception:
                    args = {}
                result = fn(args) if fn else {"error": f"Unknown tool {tc.function.name}"}
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _serialize(result),
                })

        return {"reply": "I wasn't able to finish answering that — too many tool steps.", "error": None}
    except Exception as e:
        return {"reply": "", "error": str(e)}
