"""Run the patient's test suite. Every case is one neatlogs trace in session "<--session>.<case id>".

    python -m patient.run --session exam-123 --out results.json
"""
import argparse
import json
import traceback
from concurrent.futures import ThreadPoolExecutor

import neatlogs

from agent_doctor.llm import get_client
from patient.agent import audit_expenses
from patient.cases import CASES, grade


def run_case(case: dict, session: str) -> dict:
    with neatlogs.trace(f"expense-audit:{case['id']}", session_id=f"{session}.{case['id']}", case_id=case["id"]):
        try:
            report = audit_expenses(case["receipts"])
            passed, reason = grade(report, case["expected"])
            return {"id": case["id"], "passed": passed, "reason": reason, "output": report}
        except Exception as e:
            return {
                "id": case["id"],
                "passed": False,
                "reason": f"crashed: {type(e).__name__}: {e}",
                "traceback": traceback.format_exc(limit=6),
            }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--session", required=True)
    parser.add_argument("--out")
    parser.add_argument("--case", help="run a single case id")
    args = parser.parse_args()

    get_client()  # init neatlogs before the first trace opens, or that trace loses its root span
    cases = [c for c in CASES if not args.case or c["id"] == args.case]
    with ThreadPoolExecutor(max_workers=len(cases)) as pool:  # each case is its own trace
        results = list(pool.map(lambda c: run_case(c, args.session), cases))
    neatlogs.flush()

    for r in results:
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {r['id']:<18} {r['reason']}")
    print(f"{sum(r['passed'] for r in results)}/{len(results)} passed")
    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
