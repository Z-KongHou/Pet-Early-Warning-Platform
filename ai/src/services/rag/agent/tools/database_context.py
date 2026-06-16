"""Database SQL query tool — lets the agent run SELECT queries directly.

Replaces all fixed-context tools. The agent writes its own SQL based on
the schema described in the system prompt.
"""

from __future__ import annotations

import logging
from typing import Any

from clients.backend_client import BackendClient

logger = logging.getLogger(__name__)


class ExecuteSqlTool:
    """Execute a read-only SELECT SQL query against the application database.

    The agent writes standard SQL SELECT statements. The backend validates
    safety (only SELECT, table whitelist, max 100 rows, sensitive columns masked).
    """

    name = "execute_sql"
    description = (
        "Execute a SELECT SQL query against the application database. "
        "Use this to answer questions about user data: pet names, breeds, ages, "
        "weights, activity scores, alert history, camera status, settings, etc. "
        "Only SELECT queries are allowed. Max 100 rows returned. "
        "Refer to the system prompt for the database schema (table and column names)."
    )
    parameters = {
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "A SELECT SQL query to execute. Use standard SQL syntax with FROM, WHERE, JOIN, ORDER BY, etc.",
            },
        },
        "required": ["sql"],
    }

    def __init__(self, backend_client: BackendClient) -> None:
        self._client = backend_client

    def execute(self, sql: str) -> str:
        result = self._client.execute_query(sql)

        error = result.get("error")
        if error:
            return f"Query failed: {error}"

        rows = result.get("rows", [])
        count = result.get("count", 0)

        if not rows:
            return "Query returned 0 rows."

        return _format_rows(rows, count)


def _format_rows(rows: list[dict[str, Any]], total: int) -> str:
    lines = [f"Query returned {total} row(s):\n"]
    # Use a compact table-like format
    if not rows:
        return lines[0]

    # Column headers
    cols = list(rows[0].keys())
    header = " | ".join(cols)
    sep = "-" * len(header)
    lines.append(header)
    lines.append(sep)

    for row in rows:
        values = [str(row.get(c, "")) for c in cols]
        lines.append(" | ".join(values))

    return "\n".join(lines)
