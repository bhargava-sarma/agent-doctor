"""Ground-truth test cases for the expense auditor. The Doctor must never edit this file."""

CASES = [
    {
        "id": "india-offsite",
        "receipts": "Team dinner in Bangalore: ₹4,500 (meal)\nAirport taxi: ₹1,200 (taxi)\nHotel in Berlin, 1 night: €150 (hotel)",
        "expected": {"total": 231.72, "violations": []},
    },
    {
        "id": "london-visit",
        "receipts": "Hotel in London, 1 night: £180 (hotel)\nClient dinner: £45 (meal)\nBlack cab: £20 (taxi)",
        "expected": {"total": 310.13, "violations": ["lodging"]},
    },
    {
        "id": "tokyo-conference",
        "receipts": "Omakase dinner: ¥15,000 (meal)\nTaxi from Narita: ¥9,000 (taxi)\nBusiness hotel: ¥27,000 (hotel)",
        "expected": {"total": 340.00, "violations": ["meals"]},
    },
    {
        "id": "mixed-currencies",
        "receipts": "Lunch in NYC: $40 (meal)\nTaxi in Paris: €70 (taxi)\nHotel in Mumbai: ₹15,000 (hotel)",
        "expected": {"total": 296.81, "violations": ["transport"]},
    },
]

# Agents may name categories either way; grading normalises to policy names.
CATEGORY_ALIASES = {"meal": "meals", "hotel": "lodging", "taxi": "transport"}


def grade(report: dict, expected: dict) -> tuple[bool, str]:
    total = report.get("total")
    violations = sorted(CATEGORY_ALIASES.get(v, v) for v in report.get("violations", []))
    if total is None or abs(float(total) - expected["total"]) > 0.5:
        return False, f"total {total} != expected {expected['total']}"
    if violations != sorted(expected["violations"]):
        return False, f"violations {violations} != expected {expected['violations']}"
    return True, "ok"
