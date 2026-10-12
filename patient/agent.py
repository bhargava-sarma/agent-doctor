"""Expense-auditor agent: converts a trip's receipts to USD, totals them, and flags policy violations."""
import json

import neatlogs

from agent_doctor.llm import PATIENT_MODEL, get_client
from patient.tools import TOOL_FUNCTIONS, TOOL_SCHEMAS

MAX_STEPS = 12

SYSTEM_PROMPT = """You are an expense auditor. For the receipts you are given:
1. Convert every item to USD using get_exchange_rate (multiply the amount by the rate).
2. Use calculate for all arithmetic.
3. Run check_policy on every item.
4. When done, reply with ONLY a JSON object, no prose:
   {"total_usd": <number rounded to 2 decimals>, "violations": [<category of each item over its limit>]}"""


@neatlogs.span(kind="AGENT")
def audit_expenses(receipts: str) -> dict:
    client = get_client()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": receipts}]

    for _ in range(MAX_STEPS):
        response = client.chat.completions.create(model=PATIENT_MODEL, messages=messages, tools=TOOL_SCHEMAS)
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return parse_report(msg.content)

        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            result = TOOL_FUNCTIONS[call.function.name](**args)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)})

    raise RuntimeError(f"agent did not finish within {MAX_STEPS} steps")


def parse_report(text: str) -> dict:
    data = json.loads(text.strip().removeprefix("```json").removesuffix("```"))
    return {"total": float(data["total_usd"]), "violations": sorted(data["violations"])}
