"""Agent Doctor: examines a failing agent through its neatlogs traces, patches it, and proves the fix."""
import json
import subprocess
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import httpx
import neatlogs

from agent_doctor import ui
from agent_doctor.llm import DOCTOR_MODEL, ROOT, get_client
from agent_doctor.neatlogs_api import NeatlogsAPI

PATIENT_DIR = ROOT / "patient"
# Ground truth and the test harness are off limits: the Doctor fixes the agent, not the exam.
PROTECTED = {"patient/cases.py", "patient/run.py"}
MAX_TRACE_CHARS = 7000
MAX_TRACES_PER_ROUND = 3

DOCTOR_PROMPT = """You are Agent Doctor, an expert at debugging LLM agents from their execution traces.

You get: the agent's source code, its test results, and neatlogs traces of the failing runs
(every LLM call, tool call, arguments, outputs and exceptions).

Find the ROOT CAUSE of the failures. Ground every claim in the traces: quote the span, tool
arguments or error that proves it. Fix the agent's code, never the tests. Prefer the smallest
change that fixes the root cause. Failures can be layered: a crash may hide a logic bug that only
shows once the crash is fixed, so fix what the evidence supports and keep tool contracts consistent.

Reply with ONLY a JSON object:
{
  "diagnosis": "<one-line headline of the bug>",
  "root_cause": "<2-4 sentences explaining why the agent fails>",
  "evidence": ["<quote or fact from a trace>", ...],
  "edits": [{"file": "patient/<file>.py", "find": "<exact unique snippet>", "replace": "<new snippet>"}]
}
Each "find" must match the current file exactly once, including whitespace."""


@dataclass
class Exam:
    session: str
    results: list[dict]
    traces: list[dict] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(r["passed"] for r in self.results)

    @property
    def crashes(self) -> int:
        return sum(r["reason"].startswith("crashed") for r in self.results)

    @property
    def score(self) -> tuple[int, int]:
        return (self.passed, -self.crashes)

    def totals(self) -> dict:
        return {
            "tokens": sum(t.get("totalTokens") or 0 for t in self.traces),
            "cost": sum(t.get("totalCostUsd") or 0 for t in self.traces),
            "llm_calls": sum(t.get("llmCallsCount") or 0 for t in self.traces),
            "tool_calls": sum(t.get("toolCallsCount") or 0 for t in self.traces),
        }


class Doctor:
    def __init__(self, max_rounds: int = 4, open_pr: bool = True):
        self.client = get_client()
        self.api = NeatlogsAPI()
        self.max_rounds = max_rounds
        self.open_pr = open_pr
        self.stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.branch = f"doctor/heal-{self.stamp}"
        self.run_dir = ROOT / ".doctor_runs" / self.stamp
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.history: list[dict] = []

    # ---- examination -------------------------------------------------------------------------

    @neatlogs.span(kind="TOOL")
    def examine(self, label: str) -> Exam:
        session = f"exam-{self.stamp}-{label}-{uuid.uuid4().hex[:4]}"
        out = self.run_dir / f"{label}.json"
        ui.step(f"Examining patient  [dim](session {session})[/]")
        subprocess.run(
            [sys.executable, "-m", "patient.run", "--session", session, "--out", str(out)],
            cwd=ROOT, capture_output=True, text=True, timeout=900,
        )
        exam = Exam(session, json.loads(out.read_text()))
        ui.step("Pulling traces from neatlogs")
        by_case = self.api.case_traces(session, [r["id"] for r in exam.results])
        exam.traces = [{**t, "case": case_id} for case_id, t in by_case.items()]
        ui.exam_table(exam)
        return exam

    def trace_evidence(self, exam: Exam) -> str:
        """Rebuild the failing runs from their neatlogs spans: the Doctor's primary evidence."""
        by_case = {t["case"]: t for t in exam.traces}
        sections = []
        for r in [r for r in exam.results if not r["passed"]][:MAX_TRACES_PER_ROUND]:
            trace = by_case.get(r["id"])
            if not trace:
                sections.append(f"### case {r['id']}: no trace found in neatlogs")
                continue
            try:
                timeline = self.api.timeline(trace["traceId"])
            except httpx.HTTPStatusError as e:
                # Trace not finalized yet: fall back to the local traceback for this case.
                timeline = f"(trace spans unavailable: HTTP {e.response.status_code})\n{r.get('traceback', '')}"
            if len(timeline) > MAX_TRACE_CHARS:
                timeline = timeline[: MAX_TRACE_CHARS // 2] + "\n...[truncated]...\n" + timeline[-MAX_TRACE_CHARS // 2 :]
            sections.append(f"### case {r['id']} - trace {trace['traceId']} (status {trace.get('status')})\n{timeline}")
        return "\n\n".join(sections)

    # ---- diagnosis & treatment ---------------------------------------------------------------

    @neatlogs.span(kind="AGENT")
    def diagnose(self, exam: Exam) -> dict:
        ui.step(f"Diagnosing with {DOCTOR_MODEL}")
        sources = "\n\n".join(
            f"=== {p.relative_to(ROOT)} ===\n{p.read_text()}"
            for p in sorted(PATIENT_DIR.glob("*.py"))
            if str(p.relative_to(ROOT)) not in PROTECTED and p.name != "__init__.py"
        )
        results = json.dumps([{k: v for k, v in r.items() if k != "traceback"} for r in exam.results], indent=1)
        history = json.dumps(self.history, indent=1) if self.history else "none"
        user = (
            f"## Agent source\n{sources}\n\n## Test results\n{results}\n\n"
            f"## Previous treatment rounds\n{history}\n\n## neatlogs traces of failing runs\n{self.trace_evidence(exam)}"
        )
        response = self.client.chat.completions.create(
            model=DOCTOR_MODEL,
            messages=[{"role": "system", "content": DOCTOR_PROMPT}, {"role": "user", "content": user}],
            max_tokens=4000,
        )
        text = response.choices[0].message.content.strip()
        text = text[text.find("{") : text.rfind("}") + 1]
        plan = json.loads(text)
        ui.diagnosis(plan)
        return plan

    def apply(self, edits: list[dict]) -> list[str]:
        """Apply find/replace edits; everything is validated before any file is written."""
        pending: dict[Path, str] = {}
        for e in edits:
            if e["file"] in PROTECTED or not e["file"].startswith("patient/"):
                raise ValueError(f"refusing to edit {e['file']}")
            path = ROOT / e["file"]
            text = pending.get(path, path.read_text())
            if text.count(e["find"]) != 1:
                raise ValueError(f"'find' snippet matched {text.count(e['find'])} times in {e['file']}")
            pending[path] = text.replace(e["find"], e["replace"])
        for path, text in pending.items():
            path.write_text(text)
        ui.patch(edits)
        return [str(p.relative_to(ROOT)) for p in pending]

    def revert(self, files: list[str]):
        subprocess.run(["git", "checkout", "--", *files], cwd=ROOT, check=True)

    def commit(self, plan: dict, files: list[str], before: Exam, after: Exam):
        msg = (
            f"Doctor: {plan['diagnosis']}\n\n{plan['root_cause']}\n\n"
            f"Tests: {before.passed}/{len(before.results)} -> {after.passed}/{len(after.results)} passing\n"
            f"Evidence session: {before.session}\nVerified in session: {after.session}"
        )
        git(["add", *files])
        git(["commit", "-m", msg])

    # ---- main loop ---------------------------------------------------------------------------

    @neatlogs.span(kind="WORKFLOW")
    def heal(self) -> dict:
        ui.banner()
        start_branch = git(["rev-parse", "--abbrev-ref", "HEAD"]).strip()
        if git(["status", "--porcelain", "patient"]).strip():
            raise RuntimeError("patient/ has uncommitted changes; commit or stash them first")
        git(["checkout", "-b", self.branch])

        first = current = self.examine("intake")
        round_no = 0
        while current.passed < len(current.results) and round_no < self.max_rounds:
            round_no += 1
            ui.round_header(round_no, self.max_rounds)
            try:
                plan = self.diagnose(current)
                files = self.apply(plan["edits"])
            except (ValueError, KeyError, json.JSONDecodeError) as e:
                ui.warn(f"Treatment plan unusable: {e}")
                self.history.append({"round": round_no, "error": str(e)})
                continue

            after = self.examine(f"round{round_no}")
            outcome = {
                "round": round_no, "diagnosis": plan["diagnosis"], "files": files,
                "before": f"{current.passed}/{len(current.results)}", "after": f"{after.passed}/{len(after.results)}",
                "after_failures": [r["reason"] for r in after.results if not r["passed"]],
            }
            if after.score > current.score:
                self.commit(plan, files, current, after)
                ui.ok(f"Improvement verified in traces: {outcome['before']} -> {outcome['after']}. Committed.")
                outcome["kept"] = True
                current = after
            else:
                self.revert(files)
                ui.warn(f"No improvement ({outcome['before']} -> {outcome['after']}). Patch reverted.")
                outcome["kept"] = False
            self.history.append(outcome)

        report = self.write_report(first, current)
        if any(h.get("kept") for h in self.history) and self.open_pr:
            self.publish(report, first, current)
        else:
            git(["checkout", start_branch])
        ui.summary(first, current)
        return {"before": first.passed, "after": current.passed, "branch": self.branch}

    # ---- reporting ---------------------------------------------------------------------------

    def write_report(self, first: Exam, last: Exam) -> Path:
        b, a = first.totals(), last.totals()
        lines = [
            f"# Agent Doctor report - {self.stamp}",
            "",
            f"**Result:** {first.passed}/{len(first.results)} -> **{last.passed}/{len(last.results)}** test cases passing",
            "",
            "| | Before | After |",
            "|---|---|---|",
            f"| Passing cases | {first.passed}/{len(first.results)} | {last.passed}/{len(last.results)} |",
            f"| Crashes | {first.crashes} | {last.crashes} |",
            f"| LLM calls | {b['llm_calls']} | {a['llm_calls']} |",
            f"| Tool calls | {b['tool_calls']} | {a['tool_calls']} |",
            f"| Tokens | {b['tokens']} | {a['tokens']} |",
            "",
            f"neatlogs sessions: before `{first.session}`, after `{last.session}`",
            "",
            "## Treatment log",
        ]
        for h in self.history:
            if "error" in h:
                lines.append(f"- Round {h['round']}: plan rejected ({h['error']})")
            else:
                verdict = "kept" if h["kept"] else "reverted"
                lines.append(f"- Round {h['round']}: **{h['diagnosis']}** ({h['before']} -> {h['after']}, {verdict})")
        path = ROOT / "reports" / f"heal-{self.stamp}.md"
        path.parent.mkdir(exist_ok=True)
        path.write_text("\n".join(lines) + "\n")
        git(["add", str(path.relative_to(ROOT))])
        git(["commit", "-m", f"Doctor: add healing report {self.stamp}"])
        return path

    def publish(self, report: Path, first: Exam, last: Exam):
        ui.step(f"Pushing {self.branch} and opening a pull request")
        token_helper = "!f(){ echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"
        git(["-c", "credential.helper=", "-c", f"credential.helper={token_helper}", "push", "-u", "origin", self.branch])
        title = f"Agent Doctor: patient healed ({first.passed}/{len(first.results)} -> {last.passed}/{len(last.results)})"
        body = report.read_text() + "\n\n🤖 Opened autonomously by Agent Doctor"
        pr = subprocess.run(
            ["gh", "pr", "create", "--head", self.branch, "--title", title, "--body", body],
            cwd=ROOT, capture_output=True, text=True,
        )
        ui.ok(f"Pull request: {pr.stdout.strip()}" if pr.returncode == 0 else f"PR failed: {pr.stderr.strip()}")


def git(args: list[str]) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout
