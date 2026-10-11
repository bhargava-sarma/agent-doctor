"""Tools for the expense-auditor agent."""
import neatlogs

# How many units of each currency one US dollar buys.
USD_RATES = {"USD": 1.0, "INR": 83.0, "EUR": 0.92, "GBP": 0.79, "JPY": 150.0}

# Per-item reimbursement limits in USD.
POLICY_LIMITS_USD = {"meals": 75.0, "lodging": 200.0, "transport": 60.0}


@neatlogs.span(kind="TOOL")
def get_exchange_rate(currency: str) -> float:
    """Multiplier that converts an amount in `currency` into USD."""
    return USD_RATES[currency.upper()]


@neatlogs.span(kind="TOOL")
def calculate(expression: str) -> float:
    """Evaluate a basic arithmetic expression."""
    allowed = set("0123456789.+-*/() ")
    if not set(expression) <= allowed:
        raise ValueError(f"unsupported characters in expression: {expression!r}")
    return round(eval(expression), 2)


@neatlogs.span(kind="TOOL")
def check_policy(category: str, amount_usd: float) -> dict:
    """Check one expense item against the company travel policy."""
    limit = POLICY_LIMITS_USD[category]
    return {"category": category, "amount_usd": amount_usd, "limit_usd": limit, "violation": amount_usd > limit}


TOOL_FUNCTIONS = {
    "get_exchange_rate": get_exchange_rate,
    "calculate": calculate,
    "check_policy": check_policy,
}

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_exchange_rate",
            "description": "Returns the multiplier that converts an amount in the given currency into USD.",
            "parameters": {
                "type": "object",
                "properties": {"currency": {"type": "string", "description": "ISO code, e.g. INR, EUR"}},
                "required": ["currency"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Evaluates an arithmetic expression such as '4500 * 0.012 + 85'.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_policy",
            "description": "Checks a single expense item (already converted to USD) against the travel policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "enum": ["meal", "hotel", "taxi"]},
                    "amount_usd": {"type": "number"},
                },
                "required": ["category", "amount_usd"],
            },
        },
    },
]
