"""Smart Query Graph state definition — SQLBot-style NL2SQL pipeline."""

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class QueryState(TypedDict):
    # ── Input ──
    question: str  # User's natural language question
    datasource_id: str  # Data source ID
    conversation_id: Optional[str]
    chat_history: List[Dict[str, str]]
    tenant_id: str
    user_permissions: List[str]

    # ── Step 1: Intent Recognition ──
    detected_intent: Dict[str, Any]
    # {"type": "aggregation"|"trend"|"comparison"|"ranking"|"detail"|"definition"|"ambiguous",
    #  "confidence": 0.0-1.0}

    # ── Step 2: NL Understanding → Structured Intent ──
    structured_intent: Dict[str, Any]
    # {
    #   "metrics": [{"name","aggregation","expr","unit"}],
    #   "dimensions": [{"name","column_name"}],
    #   "filters": [{"column","operator","value"}],
    #   "time_range": {"start","end","type"},
    #   "sort": [{"column","order":"asc|desc"}],
    #   "limit": int
    # }

    # ── Few-shot Retrieval ──
    selected_examples: List[Dict[str, Any]]  # Matched SQL examples

    # ── Step 3: SQL Compilation ──
    generated_sql: str  # Raw LLM-generated SQL

    # ── SQL Guard ──
    guarded_sql: str  # Post-guard SQL (may be rewritten)
    guard_warnings: List[str]
    guard_errors: List[str]

    # ── Execution ──
    execution_result: Dict[str, Any]
    # {"columns":[str], "rows":[[Any]], "row_count":int,
    #  "executed_sql":str, "execution_time_ms":float}
    error_info: Dict[str, Any]  # If execution failed

    # ── Analysis & Output ──
    analysis_text: str  # AI-generated text analysis
    chart_recommendation: Dict[str, Any]  # {type, config}
    natural_response: str  # Final formatted response

    # ── Metadata ──
    metadata: Dict[str, Any]  # {sql, tokens, latency, confidence, retry_count}
