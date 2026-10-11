"""python -m agent_doctor heal [--max-rounds N] [--no-pr]"""
import argparse

import neatlogs

from agent_doctor.doctor import Doctor


def main():
    parser = argparse.ArgumentParser(prog="agent_doctor")
    sub = parser.add_subparsers(dest="command", required=True)
    heal = sub.add_parser("heal", help="examine, diagnose and repair the patient agent")
    heal.add_argument("--max-rounds", type=int, default=4)
    heal.add_argument("--no-pr", action="store_true", help="commit locally but don't push or open a PR")
    args = parser.parse_args()

    doctor = Doctor(max_rounds=args.max_rounds, open_pr=not args.no_pr)
    with neatlogs.trace("agent-doctor:heal", session_id=f"doctor-{doctor.stamp}"):
        doctor.heal()
    neatlogs.flush()


if __name__ == "__main__":
    main()
