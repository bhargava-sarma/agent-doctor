"""Read traces back from the neatlogs public API so the Doctor can examine them."""
import os
import time

import httpx

BASE_URL = os.getenv("NEATLOGS_API_URL", "https://app.neatlogs.com/api/v1/public")


class NeatlogsAPI:
    def __init__(self):
        key = os.getenv("NEATLOGS_PUBLIC_API_KEY")
        if not key:
            raise RuntimeError("NEATLOGS_PUBLIC_API_KEY is not set (neatlogs Settings -> API keys -> public API key)")
        key = key.strip()
        # Service-account tokens (nlsa_) go in Authorization; legacy project keys use x-api-key.
        headers = {"Authorization": f"Bearer {key}"} if key.startswith("nlsa_") else {"x-api-key": key}
        self.http = httpx.Client(base_url=BASE_URL, headers=headers, timeout=30)
        project_id = os.getenv("NEATLOGS_PROJECT_ID") or self._default_project_id()
        self.http.headers["x-project-id"] = project_id

    def _default_project_id(self) -> str:
        projects = self._get("/projects")["projects"]
        return next((p for p in projects if p.get("isDefault")), projects[0])["id"]

    def _get(self, path: str, retry_s: int = 30, **params):
        deadline = time.time() + retry_s
        while True:
            resp = self.http.get(path, params={k: v for k, v in params.items() if v is not None})
            # 409 TRACE_PROCESSING: spans are readable only once the trace is finalized.
            if resp.status_code in (409, 429) and time.time() < deadline:
                time.sleep(3)
                continue
            resp.raise_for_status()
            return resp.json()["data"]

    def case_traces(self, session: str, case_ids: list[str], wait_s: int = 60) -> dict[str, dict]:
        """Map each test case to its trace (session "<session>.<case id>"), polling until ingested."""
        found: dict[str, dict] = {}
        deadline = time.time() + wait_s
        while True:
            for case_id in case_ids:
                if case_id not in found:
                    traces = self._get("/traces", sessionId=f"{session}.{case_id}", limit=1)["traces"]
                    if traces:
                        found[case_id] = traces[0]
            if len(found) == len(case_ids) or time.time() > deadline:
                return found
            time.sleep(3)

    def spans(self, trace_id: str) -> list[dict]:
        spans = self._get(f"/traces/{trace_id}/spans", limit=50)["spans"]
        return sorted(spans, key=lambda s: s["startedAt"])

    def payload(self, trace_id: str, span_id: str) -> dict:
        fields = self._get(f"/traces/{trace_id}/spans/{span_id}/payload", fields="error,input,output")["fields"]
        return {k: v["value"] for k, v in fields.items() if v.get("available")}

    def timeline(self, trace_id: str, max_field: int = 600) -> str:
        """Step-by-step account of a trace: every span with its inputs, outputs and errors."""
        lines = []
        for i, s in enumerate(self.spans(trace_id), 1):
            lines.append(f"{i}. [{s['spanType']}] {s['spanName']} status={s['status']} {s.get('durationMs') or 0:.0f}ms")
            if s["spanType"] in ("TOOL", "AGENT", "LLM") or s["status"] != "OK":
                for key, value in self.payload(trace_id, s["spanId"]).items():
                    if s["spanType"] == "LLM" and key == "input":
                        value = value[-max_field:]  # conversation so far; the tail is what's new
                    lines.append(f"   {key}: {str(value)[:max_field]}")
        return "\n".join(lines)
