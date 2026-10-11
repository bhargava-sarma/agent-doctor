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
        headers = {"x-api-key": key}
        if project_id := os.getenv("NEATLOGS_PROJECT_ID"):
            headers["x-project-id"] = project_id
        self.http = httpx.Client(base_url=BASE_URL, headers=headers, timeout=30)

    def _get(self, path: str, **params):
        resp = self.http.get(path, params={k: v for k, v in params.items() if v is not None})
        resp.raise_for_status()
        return resp.json()["data"]

    def session_traces(self, session_id: str, expected: int, wait_s: int = 60) -> list[dict]:
        """Traces for one run, polling until all `expected` traces have been ingested."""
        deadline = time.time() + wait_s
        while True:
            traces = self._get("/traces", sessionId=session_id, limit=50)["traces"]
            if len(traces) >= expected or time.time() > deadline:
                return traces
            time.sleep(3)

    def spans(self, trace_id: str) -> list[dict]:
        return self._get(f"/traces/{trace_id}/spans", limit=50)["spans"]

    def export_markdown(self, trace_id: str) -> str:
        resp = self.http.get(f"/traces/{trace_id}/export", params={"format": "markdown"})
        resp.raise_for_status()
        if resp.headers.get("content-type", "").startswith("application/json"):
            data = resp.json().get("data")
            return data if isinstance(data, str) else str(data)
        return resp.text
