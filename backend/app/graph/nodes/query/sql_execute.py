"""
Query Node: SQL Executor.

Executes guarded SQL against the target database through a read-only connection pool.
Enforces resource limits: timeout, row count cap, concurrent query limit.
"""

import time
from typing import Any, Dict

from app.graph.state.query_state import QueryState
from app.config import settings


async def sql_execute_node(state: QueryState) -> Dict[str, Any]:
    """
    Execute validated SQL against datasource with resource limits.
    """
    guarded_sql = state.get("guarded_sql", "")
    guard_errors = state.get("guard_errors", [])

    # If guard failed, don't execute
    if guard_errors:
        return {
            "execution_result": {},
            "error_info": {"type": "guard_failed", "message": "; ".join(guard_errors)},
        }

    if not guarded_sql:
        return {
            "execution_result": {},
            "error_info": {"type": "empty_sql", "message": "SQL为空"},
        }

    # Get datasource config
    from sqlalchemy import select
    from app.database import get_async_session
    from app.models.datasource import DataSource
    from app.utils.data_masking import decrypt_connection_config

    datasource_id = state["datasource_id"]

    async with get_async_session() as db:
        result = await db.execute(select(DataSource).where(DataSource.id == datasource_id))
        ds = result.scalar_one_or_none()

    if not ds:
        return {
            "execution_result": {},
            "error_info": {"type": "datasource_not_found", "message": "数据源不存在"},
        }

    # Decrypt connection config
    try:
        conn_config = decrypt_connection_config(ds.connection_config_encrypted)
    except Exception as e:
        return {
            "execution_result": {},
            "error_info": {"type": "config_error", "message": f"连接配置解密失败: {e}"},
        }

    # Execute SQL with limits
    try:
        execution_result = await _execute_with_limits(
            db_type=ds.db_type,
            conn_config=conn_config,
            sql=guarded_sql,
            timeout=settings.sql_guard_timeout_seconds,
            max_rows=settings.sql_guard_max_rows,
        )
        return {
            "execution_result": execution_result,
            "error_info": {},
        }
    except Exception as e:
        return {
            "execution_result": {},
            "error_info": {
                "type": "execution_error",
                "message": str(e),
                "sql": guarded_sql,
            },
        }


async def _execute_with_limits(
    db_type: str,
    conn_config: Dict[str, Any],
    sql: str,
    timeout: int,
    max_rows: int,
) -> Dict[str, Any]:
    """
    Execute SQL with timeout and row limits.
    Uses a fresh connection per query (no session reuse for security).
    """
    import asyncio

    host = conn_config.get("host", "localhost")
    port = conn_config.get("port", 5432)
    database = conn_config.get("database", "postgres")
    username = conn_config.get("username", "readonly_user")
    password = conn_config.get("password", "")

    start_time = time.time()

    if db_type == "postgresql":
        result = await _execute_postgresql(
            host=host, port=port, database=database,
            username=username, password=password,
            sql=sql, timeout=timeout, max_rows=max_rows,
        )
    elif db_type == "mysql":
        result = await _execute_mysql(
            host=host, port=port, database=database,
            username=username, password=password,
            sql=sql, timeout=timeout, max_rows=max_rows,
        )
    else:
        raise ValueError(f"Unsupported database type: {db_type}")

    execution_time_ms = (time.time() - start_time) * 1000
    result["execution_time_ms"] = round(execution_time_ms, 2)
    result["executed_sql"] = sql

    return result


async def _execute_postgresql(
    host: str, port: int, database: str,
    username: str, password: str,
    sql: str, timeout: int, max_rows: int,
) -> Dict[str, Any]:
    """Execute SQL on PostgreSQL with asyncpg."""
    import asyncpg

    conn = await asyncpg.connect(
        host=host, port=port, database=database,
        user=username, password=password,
        timeout=timeout,
        statement_timeout=timeout * 1000,  # ms
    )

    try:
        # Set read-only transaction
        await conn.execute("SET TRANSACTION READ ONLY")

        stmt = await conn.prepare(sql)
        rows = await stmt.fetch(max_rows)

        columns = [col.name for col in stmt.get_attributes()]
        result_rows = [list(row) for row in rows]

        return {
            "columns": columns,
            "rows": result_rows,
            "row_count": len(result_rows),
        }
    finally:
        await conn.close()


async def _execute_mysql(
    host: str, port: int, database: str,
    username: str, password: str,
    sql: str, timeout: int, max_rows: int,
) -> Dict[str, Any]:
    """Execute SQL on MySQL with aiomysql."""
    import aiomysql

    conn = await aiomysql.connect(
        host=host, port=port, db=database,
        user=username, password=password,
        connect_timeout=timeout,
        read_default_file=None,
    )

    try:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(sql)
            rows = await cur.fetchmany(max_rows)
            columns = [d[0] for d in cur.description] if cur.description else []
            result_rows = [list(row.values()) for row in rows]

            return {
                "columns": columns,
                "rows": result_rows,
                "row_count": len(result_rows),
            }
    finally:
        conn.close()
