from pathlib import Path
from datetime import datetime
import json
import re
import sqlite3

from mcp.server.fastmcp import FastMCP
from sqlite_helper import create_db, load_csv_to_table

mcp = FastMCP("data-query-builder")

# In-memory database for this server session
conn = create_db()

# Dynamic action history for this session
history: list[dict] = []

# Reject non-read-only SQL
FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b(drop|delete|alter|insert|update|replace|create|attach|detach|pragma)\b",
    re.IGNORECASE,
)


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    return datetime.utcnow().isoformat() + "Z"


def _add_history(action: str, details: dict) -> None:
    """Append an action entry to the in-memory history."""
    history.append(
        {
            "timestamp": _now(),
            "action": action,
            "details": details,
        }
    )


def _fetch_table_names() -> list[str]:
    """Return all user table names currently present in the database."""
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
        ORDER BY name
        """
    ).fetchall()
    return [row["name"] for row in rows]


def _table_exists(table_name: str) -> bool:
    """Return True if the given table exists in the current SQLite database."""
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        LIMIT 1
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _column_info(table_name: str) -> list[sqlite3.Row]:
    """Return PRAGMA table_info rows for a table."""
    return conn.execute(f'PRAGMA table_info("{table_name}")').fetchall()


def _schema_as_dict() -> dict:
    """Return the current database schema as a Python dictionary."""
    schema: dict[str, list[dict[str, str]]] = {}

    for table_name in _fetch_table_names():
        columns = _column_info(table_name)
        schema[table_name] = [
            {
                "name": col["name"],
                "type": col["type"],
            }
            for col in columns
        ]

    return schema


def _format_rows(rows: list[sqlite3.Row]) -> str:
    """Format SQLite rows into readable JSON."""
    if not rows:
        return "No rows returned."

    data = [dict(row) for row in rows]
    return json.dumps(data, indent=2, ensure_ascii=False)


def _column_exists(table_name: str, column: str) -> bool:
    """Return True if the column exists in the given table."""
    columns = _column_info(table_name)
    return any(col["name"] == column for col in columns)


def _column_type(table_name: str, column: str) -> str | None:
    """Return the declared SQLite type for a column, or None if missing."""
    columns = _column_info(table_name)
    for col in columns:
        if col["name"] == column:
            return str(col["type"]).upper()
    return None


def _available_columns(table_name: str) -> list[str]:
    """Return available column names for a table."""
    return [col["name"] for col in _column_info(table_name)]


def _table_row_count(table_name: str) -> int:
    """Return row count for a table."""
    row = conn.execute(f'SELECT COUNT(*) AS row_count FROM "{table_name}"').fetchone()
    return int(row["row_count"])


# - Tools -

@mcp.prompt("expert-data-analysis")
def expert_analysis_prompt() -> str:
    """Template pour transformer l'IA en Analyste Senior Discipliné."""
    return """You are a senior data analyst. You must work methodically using the provided tools.
Follow this 4-phase workflow for every request:

Phase 1 – Data Preparation:
•⁠  ⁠Use 'load_csv' to ingest the dataset.
•⁠  ⁠Use 'describe_schema' to verify column names and types.

Phase 2 – Revenue Analysis:
•⁠  ⁠Use 'run_query' to compute total revenue (price * quantity) per region.
•⁠  ⁠Identify top and bottom performers.

Phase 3 – Comparative Analysis:
•⁠  ⁠Use 'get_statistics' to check volumes (mean/min/max quantity).

Phase 4 – Synthesis:
•⁠  ⁠Provide a structured conclusion and cite exactly which tools gave you the results."""


@mcp.tool()
def load_csv(file_path: str, table_name: str) -> str:
    """Load a CSV file into a new in-memory SQLite table with automatic type detection.

    Use this before any analysis. It imports a CSV file, creates a SQLite table, detects column
    types automatically, and returns the table name, row count, and detected columns.
    """
    try:
        path = Path(file_path)

        if not path.exists():
            return f"Error: File not found: {file_path}"

        if not path.is_file():
            return f"Error: Path is not a file: {file_path}"

        if path.suffix.lower() != ".csv":
            return (
                f"Error: Expected a CSV file, but got: {path.name}. "
                "Please provide a .csv file."
            )

        if not table_name.strip():
            return "Error: table_name cannot be empty."

        result = load_csv_to_table(conn, str(path), table_name)

        _add_history(
            "load_csv",
            {
                "file_path": str(path),
                "table_name": result["table_name"],
                "row_count": result["row_count"],
                "columns": result["columns"],
            },
        )

        columns_text = "\n".join(
            f"- {col_name}: {col_type}"
            for col_name, col_type in result["columns"]
        )

        return (
            f"CSV loaded successfully.\n"
            f"Table: {result['table_name']}\n"
            f"Rows: {result['row_count']}\n"
            f"Columns:\n{columns_text}"
        )

    except ValueError as e:
        return f"Error: {e}"
    except sqlite3.Error as e:
        return f"SQLite error while loading CSV: {e}"
    except Exception as e:
        return f"Unexpected error while loading CSV: {e}"


@mcp.tool()
def describe_schema() -> str:
    """List all tables currently loaded in the SQLite database and show their columns with types.

    Use this after loading data to understand which tables and columns are available before
    writing a query.
    """
    try:
        table_names = _fetch_table_names()

        if not table_names:
            return "No tables are currently loaded in the database."

        parts = []
        for table_name in table_names:
            columns = _column_info(table_name)

            if not columns:
                parts.append(f"Table: {table_name}\n  (no columns found)")
                continue

            column_lines = [
                f'  - {col["name"]}: {col["type"]}'
                for col in columns
            ]

            parts.append(f"Table: {table_name}\n" + "\n".join(column_lines))

        _add_history(
            "describe_schema",
            {
                "tables": table_names,
            },
        )

        return "\n\n".join(parts)

    except sqlite3.Error as e:
        return f"SQLite error while describing schema: {e}"
    except Exception as e:
        return f"Unexpected error while describing schema: {e}"


@mcp.tool()
def list_tables() -> str:
    """List all tables in the current SQLite database and show their row counts.

    Use this to quickly see what data is loaded and how many records each table contains.
    """
    try:
        table_names = _fetch_table_names()

        if not table_names:
            return "No tables are currently loaded in the database."

        parts = []
        counts = {}
        for table_name in table_names:
            row_count = _table_row_count(table_name)
            counts[table_name] = row_count
            parts.append(f"- {table_name}: {row_count} rows")

        _add_history(
            "list_tables",
            {
                "tables": counts,
            },
        )

        return "Current tables:\n" + "\n".join(parts)

    except sqlite3.Error as e:
        return f"SQLite error while listing tables: {e}"
    except Exception as e:
        return f"Unexpected error while listing tables: {e}"


@mcp.tool()
def preview_table(table_name: str, limit: int = 5) -> str:
    """Preview the first rows of a loaded table.

    Use this after load_csv to inspect sample records before writing SQL.
    This tool depends on a table already being loaded into the database.
    """
    try:
        if not _table_exists(table_name):
            existing = _fetch_table_names()
            if not existing:
                return (
                    f"Error: Table '{table_name}' does not exist because no tables are loaded yet. "
                    "Use load_csv first."
                )
            return (
                f"Error: Table '{table_name}' does not exist. "
                f"Available tables: {', '.join(existing)}"
            )

        if limit <= 0:
            return "Error: limit must be greater than 0."

        rows = conn.execute(
            f'SELECT * FROM "{table_name}" LIMIT ?',
            (limit,),
        ).fetchall()

        _add_history(
            "preview_table",
            {
                "table_name": table_name,
                "limit": limit,
                "returned_rows": len(rows),
            },
        )

        return (
            f"Preview of table '{table_name}' (up to {limit} rows):\n"
            f"{_format_rows(rows)}"
        )

    except sqlite3.Error as e:
        return f"SQLite error while previewing table: {e}"
    except Exception as e:
        return f"Unexpected error while previewing table: {e}"


@mcp.tool()
def run_query(sql: str, limit: int = 50) -> str:
    """Execute a read-only SQL query on the loaded SQLite tables and return up to `limit` rows.

    Use this for SELECT-style analysis after loading a CSV and inspecting the schema.
    This tool rejects dangerous write operations such as DROP, DELETE, ALTER, INSERT, and UPDATE.
    """
    try:
        cleaned_sql = sql.strip()

        if not cleaned_sql:
            return "Error: sql cannot be empty."

        if FORBIDDEN_SQL_PATTERN.search(cleaned_sql):
            return (
                "Error: Only read-only SQL queries are allowed. "
                "Forbidden keywords detected: DROP, DELETE, ALTER, INSERT, UPDATE, REPLACE, "
                "CREATE, ATTACH, DETACH, PRAGMA."
            )

        if not cleaned_sql.lower().startswith("select"):
            return (
                "Error: Only SELECT queries are allowed in run_query. "
                "Example: SELECT region, AVG(price) FROM sales GROUP BY region"
            )

        if limit <= 0:
            return "Error: limit must be greater than 0."

        final_sql = cleaned_sql.rstrip().rstrip(";") + f" LIMIT {limit}"
        rows = conn.execute(final_sql).fetchall()

        _add_history(
            "run_query",
            {
                "sql": cleaned_sql,
                "limit": limit,
                "returned_rows": len(rows),
            },
        )

        return (
            f"Query executed successfully.\n"
            f"Returned rows: {len(rows)}\n"
            f"Results:\n{_format_rows(rows)}"
        )

    except sqlite3.Error as e:
        return (
            f"SQLite error while executing query: {e}\n"
            "Tip: check table names, column names, and SQL syntax after using describe_schema."
        )
    except Exception as e:
        return f"Unexpected error while executing query: {e}"


@mcp.tool()
def get_statistics(table_name: str, column: str) -> str:
    """Compute summary statistics for a numeric column: count, min, max, mean, and null count.

    Use this when you want a quick numeric summary without writing SQL manually.
    The target table and column must already exist, and the column should be numeric.
    """
    try:
        if not _table_exists(table_name):
            existing = _fetch_table_names()
            if not existing:
                return (
                    f"Error: Table '{table_name}' does not exist because no tables are loaded yet. "
                    "Use load_csv first."
                )
            return (
                f"Error: Table '{table_name}' does not exist. "
                f"Available tables: {', '.join(existing)}"
            )

        if not _column_exists(table_name, column):
            available = _available_columns(table_name)
            return (
                f"Error: Column '{column}' does not exist in table '{table_name}'. "
                f"Available columns: {', '.join(available)}"
            )

        declared_type = _column_type(table_name, column)
        if declared_type not in {"INTEGER", "REAL"}:
            return (
                f"Error: Column '{column}' in table '{table_name}' is not numeric "
                f"(detected type: {declared_type}). "
                "Use a column with type INTEGER or REAL."
            )

        row = conn.execute(
            f'''
            SELECT
                COUNT("{column}") AS non_null_count,
                MIN("{column}") AS min_value,
                MAX("{column}") AS max_value,
                AVG("{column}") AS mean_value,
                SUM(CASE WHEN "{column}" IS NULL THEN 1 ELSE 0 END) AS null_count
            FROM "{table_name}"
            '''
        ).fetchone()

        _add_history(
            "get_statistics",
            {
                "table_name": table_name,
                "column": column,
            },
        )

        return (
            f"Statistics for {table_name}.{column}\n"
            f"- non_null_count: {row['non_null_count']}\n"
            f"- null_count: {row['null_count']}\n"
            f"- min: {row['min_value']}\n"
            f"- max: {row['max_value']}\n"
            f"- mean: {row['mean_value']}"
        )

    except sqlite3.Error as e:
        return f"SQLite error while computing statistics: {e}"
    except Exception as e:
        return f"Unexpected error while computing statistics: {e}"


# - Resources -

@mcp.resource("db://schema")
def db_schema() -> str:
    """Current database schema as JSON."""
    return json.dumps(_schema_as_dict(), indent=2, ensure_ascii=False)


@mcp.resource("db://query-history")
def db_query_history() -> str:
    """Action history for this session as JSON."""
    return json.dumps(history, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()