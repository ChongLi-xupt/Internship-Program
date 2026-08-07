"""
Query Node: SQL Guard — Security Gateway (CRITICAL).

Multi-layer SQL safety validation and rewriting:
1. Syntax check via sqlglot AST parse
2. Forbidden statement detection
3. Dangerous function detection
4. Read-only enforcement
5. Row-level permission injection
6. LIMIT enforcement
7. Sensitive column masking

This is the most security-critical node in the entire system.
NEVER trust LLM-generated SQL. Every SQL must pass through this gate.
"""

import re
from typing import Any, Dict, List, Tuple

from app.graph.state.query_state import QueryState
from app.config import settings


class SQLGuardResult:
    """Result of SQL guard validation."""

    def __init__(self):
        self.passed: bool = True
        self.sql: str = ""
        self.warnings: List[str] = []
        self.errors: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "sql": self.sql,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ── Forbidden patterns ──
FORBIDDEN_STATEMENTS = {
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER",
    "CREATE", "TRUNCATE", "GRANT", "REVOKE", "CALL",
    "EXEC", "EXECUTE",
}

DANGEROUS_FUNCTIONS = [
    "pg_sleep", "LOAD_FILE", "INTO OUTFILE",
    "benchmark(", "exec(", "xp_cmdshell",
    "lo_import", "lo_export", "pg_read_file",
    "copy ", "COPY ",  # COPY TO/FROM file
]

# Regex patterns for quick detection (before AST)
_FORBIDDEN_REGEX = re.compile(
    r"\b(" + "|".join(FORBIDDEN_STATEMENTS) + r")\b",
    re.IGNORECASE,
)

_DANGEROUS_FUNC_REGEX = re.compile(
    "(" + "|".join(re.escape(f) for f in DANGEROUS_FUNCTIONS) + ")",
    re.IGNORECASE,

)

# Sensitive column patterns for masking
_SENSITIVE_COLUMN_PATTERNS = [
    (r"(?i)(phone|mobile|cell)", "***"),
    (r"(?i)(id_card|idcard|identity|身份证)", "***"),
    (r"(?i)(password|passwd|pwd)", "***"),
    (r"(?i)(salary|工资|薪资)", "***"),
    (r"(?i)(email|邮箱)", "***@***"),
]


def _check_syntax(sql: str) -> Tuple[bool, str]:
    """Check SQL syntax using sqlglot parser."""
    try:
        import sqlglot

        parsed = sqlglot.parse_one(sql)
        return True, str(parsed)
    except Exception as e:
        return False, f"语法错误: {str(e)}"


def _check_forbidden_statements(sql: str) -> List[str]:
    """Detect forbidden DDL/DML statements."""
    errors = []
    matches = _FORBIDDEN_REGEX.findall(sql)
    if matches:
        errors.append(f"禁止的语句类型: {', '.join(set(matches).upper())}")
    return errors


def _check_dangerous_functions(sql: str) -> List[str]:
    """Detect dangerous function calls."""
    errors = []
    matches = _DANGEROUS_FUNC_REGEX.findall(sql)
    if matches:
        errors.append(f"危险函数调用: {', '.join(set(matches))}")
    return errors


def _enforce_read_only(sql: str) -> Tuple[bool, str]:
    """
    Verify SQL is read-only.
    Uses EXPLAIN (if available) or heuristic check.
    """
    # Quick heuristic: must start with SELECT or WITH (CTE)
    upper = sql.strip().upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        return False, sql  # Will be caught by forbidden statement check anyway
    return True, sql


def _inject_row_permission(sql: str, permission_condition: str) -> str:
    """Inject row-level permission WHERE clause."""
    if not permission_condition:
        return sql

    import sqlglot

    try:
        parsed = sqlglot.parse_one(sql)
        # Find existing WHERE clause and AND-append
        # Simplified: append to end before ORDER BY / GROUP BY / LIMIT
        upper_sql = sql.upper()

        # Find insertion point (before ORDER BY, LIMIT, etc.)
        insert_keywords = ["ORDER BY", "LIMIT", "OFFSET", "HAVING"]
        insert_pos = len(sql)
        lowest_pos = len(sql)

        for kw in insert_keywords:
            pos = upper_sql.rfind(kw)
            if pos > 0 and pos < lowest_pos:
                lowest_pos = pos

        if lowest_pos < len(sql):
            # Insert before the keyword
            modified = sql[:lowest_pos] + f" AND ({permission_condition}) " + sql[lowest_pos:]
        else:
            # No ORDER BY/LIMIT — append WHERE or AND
            if "WHERE" in upper_sql:
                modified = sql + f" AND ({permission_condition})"
            else:
                # Find position after FROM clause to inject WHERE
                from_pos = upper_sql.find("FROM")
                if from_pos > 0:
                    # Simple approach: find end of table references
                    modified = sql + f" WHERE {permission_condition}"
                else:
                    modified = sql

        return modified
    except Exception:
        # Fallback: simple string append
        if "WHERE" in sql.upper():
            return sql + f" AND ({permission_condition})"
        return sql + f" WHERE {permission_condition}"


def _enforce_limit(sql: str, default_limit: int) -> str:
    """Ensure LIMIT clause exists."""
    upper = sql.upper().strip()
    if upper.endswith(f"LIMIT {default_limit}") or re.search(rf"\bLIMIT\s+{default_limit}\s*$", upper):
        return sql  # Already has correct limit

    if re.search(r"\bLIMIT\s+\d+", upper):
        return sql  # Has some limit already

    return sql.rstrip(";").rstrip() + f" LIMIT {default_limit}"


def _mask_sensitive_columns(sql: str) -> Tuple[str, List[str]]:
    """Detect and mask sensitive columns in SELECT."""
    warnings = []
    masked_sql = sql

    for pattern, mask_value in _SENSITIVE_COLUMN_PATTERNS:
        # Look for pattern in SELECT column list
        select_match = re.search(
            rf"SELECT\s+(.*?)\s+FROM",
            masked_sql,
            re.IGNORECASE | re.DOTALL,
        )
        if select_match:
            select_clause = select_match.group(1)
            if re.search(pattern, select_clause):
                warnings.append(f"检测到敏感列，已应用脱敏处理")
                # Apply masking function in SELECT
                masked_select = re.sub(
                    rf"(\w*\.{0,1})(\w*{pattern}\w*)",
                    rf"\1MASK(\2)::varchar as \2_masked",
                    select_clause,
                    flags=re.IGNORECASE,
                )
                masked_sql = masked_sql.replace(select_clause, masked_select, 1)

    return masked_sql, warnings


async def sql_guard_node(state: QueryState) -> Dict[str, Any]:
    """
    Execute all SQL guard rules against generated SQL.
    Returns guarded SQL (possibly rewritten) + warnings/errors.
    """
    sql = state.get("generated_sql", "")
    user_permissions = state.get("user_permissions", [])

    guard = SQLGuardResult()
    guard.sql = sql

    if not sql:
        guard.passed = False
        guard.errors.append("SQL为空")
        return {"guarded_sql": "", "guard_warnings": [], "guard_errors": guard.errors}

    # Rule 1: Syntax check
    passed, parsed_sql = _check_syntax(sql)
    if not passed:
        guard.passed = False
        guard.errors.append(parsed_sql)
        return {"guarded_sql": sql, "guard_warnings": guard.warnings, "guard_errors": guard.errors}
    guard.sql = parsed_sql

    # Rule 2: Forbidden statements
    stmt_errors = _check_forbidden_statements(guard.sql)
    if stmt_errors:
        guard.passed = False
        guard.errors.extend(stmt_errors)
        return {"guarded_sql": sql, "guard_warnings": guard.warnings, "guard_errors": guard.errors}

    # Rule 3: Dangerous functions
    func_errors = _check_dangerous_functions(guard.sql)
    if func_errors:
        guard.passed = False
        guard.errors.extend(func_errors)
        return {"guarded_sql": sql, "guard_warnings": guard.warnings, "guard_errors": guard.errors}

    # Rule 4: Read-only enforcement
    is_ro, guard.sql = _enforce_read_only(guard.sql)
    if not is_ro:
        guard.passed = False
        guard.errors.append("非只读查询被拒绝")
        return {"guarded_sql": sql, "guard_warnings": guard.warnings, "guard_errors": guard.errors}

    # Rule 5: Row-level permission injection
    # Build permission condition from user's data scope
    # This is a simplified version — real impl would use actual RBAC rules
    perm_condition = ""
    if user_permissions:
        # Example: if user has 'region:east' permission
        region_perms = [p for p in user_permissions if p.startswith("data_scope:")]
        if region_perms:
            scopes = [p.split(":", 1)[1] for p in region_perms]
            perm_condition = f"region IN ({','.join(repr(s) for s in scopes)})"

    if perm_condition:
        guard.sql = _inject_row_permission(guard.sql, perm_condition)

    # Rule 6: LIMIT enforcement
    max_rows = settings.sql_guard_max_rows
    guard.sql = _enforce_limit(guard.sql, max_rows)

    # Rule 7: Sensitive column masking
    guard.sql, mask_warnings = _mask_sensitive_columns(guard.sql)
    guard.warnings.extend(mask_warnings)

    return {
        "guarded_sql": guard.sql,
        "guard_warnings": guard.warnings,
        "guard_errors": guard.errors,
    }
