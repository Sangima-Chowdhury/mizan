import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv
from database import get_connection

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

QUERY_TOOL_DEFINITION = {
    "name": "search_campaigns",
    "description": "Search the campaigns database using structured filters. Use this to find campaigns matching whatever the moderator is asking about.",
    "input_schema": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string",
                "enum": ["zakat", "sadaqah", "waqf", "lillah", "uncategorized"],
                "description": "Filter by giving category."
            },
            "status": {
                "type": "string",
                "enum": ["pending_review", "approved", "rejected", "escalated"],
                "description": "Filter by moderation status."
            },
            "keyword": {
                "type": "string",
                "description": "A word or phrase to search for in the campaign title or description."
            },
            "min_fraud_risk": {
                "type": "integer",
                "description": "Only return campaigns with a fraud_risk_score at or above this value."
            },
            "submitted_after": {
                "type": "string",
                "description": "Only return campaigns submitted on or after this date, formatted YYYY-MM-DD."
            },
            "submitted_before": {
                "type": "string",
                "description": "Only return campaigns submitted on or before this date, formatted YYYY-MM-DD."
            }
        }
    }
}

QUERY_SYSTEM_PROMPT = """You are a moderator assistant for Mizan, a campaign intake system for an Islamic crowdfunding platform. Moderators ask you natural language questions about past campaigns — for example, an old campaign they can't remember the exact name or date of.

Use the search_campaigns tool to look up real data before answering. Never guess or make up campaign details. If the moderator's question is vague, choose the filters that best match their intent — for example, "that medical campaign from a few months back" should search using a keyword like "medical".
You get exactly one search per question. Do not say you will search again, broaden, or follow up — answer directly and completely from the one search you get.
After you get results back, answer in plain, direct language. Mention specific campaign titles, IDs, and statuses so the moderator can act on your answer. If nothing matches, say so clearly rather than guessing.
Reply in plain text with no markdown formatting, and use simple line breaks between campaigns.
"""


def build_query(filters):
    """Turn a dict of filters into a safe, parameterized SQL query.
    Every value is passed separately via %s — never interpolated into the SQL string,
    even though these values are coming from Claude, not directly from a person."""
    conditions = []
    values = []

    if filters.get("category"):
        conditions.append("category = %s")
        values.append(filters["category"])

    if filters.get("status"):
        conditions.append("status = %s")
        values.append(filters["status"])

    if filters.get("keyword"):
        conditions.append("(title ILIKE %s OR description ILIKE %s)")
        like_value = f"%{filters['keyword']}%"
        values.append(like_value)
        values.append(like_value)

    if filters.get("min_fraud_risk") is not None:
        conditions.append("fraud_risk_score >= %s")
        values.append(filters["min_fraud_risk"])

    if filters.get("submitted_after"):
        conditions.append("submitted_at >= %s")
        values.append(filters["submitted_after"])

    if filters.get("submitted_before"):
        conditions.append("submitted_at <= %s")
        values.append(filters["submitted_before"])

    where_clause = " AND ".join(conditions) if conditions else "TRUE"

    query = f"""
        SELECT id, title, description, category, status,
               fraud_risk_score, policy_risk_score, submitted_at, reviewed_at
        FROM campaigns
        WHERE {where_clause}
        ORDER BY submitted_at DESC
        LIMIT 20;
    """
    return query, values


def run_search(filters):
    conn = get_connection()
    cursor = conn.cursor()

    query, values = build_query(filters)
    cursor.execute(query, values)

    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    results = [dict(zip(columns, row)) for row in rows]

    cursor.close()
    conn.close()
    return results


def ask_moderator_assistant(question):
    messages = [{"role": "user", "content": question}]

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1500,
        system=QUERY_SYSTEM_PROMPT,
        tools=[QUERY_TOOL_DEFINITION],
        messages=messages
    )

    if response.stop_reason == "tool_use":
        tool_call = next(
            block for block in response.content if block.type == "tool_use")
        filters = tool_call.input
        results = run_search(filters)

        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [{
                "type": "tool_result",
                "tool_use_id": tool_call.id,
                "content": json.dumps(results, default=str)
            }]
        })

        final_response = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1500,
            system=QUERY_SYSTEM_PROMPT,
            tools=[QUERY_TOOL_DEFINITION],
            messages=messages
        )

        answer_text = "".join(
            block.text for block in final_response.content if block.type == "text")
        return {"answer": answer_text, "filters_used": filters, "result_count": len(results)}

    answer_text = "".join(
        block.text for block in response.content if block.type == "text")
    return {"answer": answer_text, "filters_used": None, "result_count": 0}
