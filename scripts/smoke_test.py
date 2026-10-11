"""Verify LiteLLM + neatlogs wiring: one traced call, then read it back via the public API."""
import os
import time
import uuid

import httpx
import neatlogs
from neatlogs.openai import wrap_openai_client
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
neatlogs.init(api_key=os.environ["NEATLOGS_API_KEY"])

client = wrap_openai_client(
    OpenAI(base_url=os.environ["LITELLM_BASE_URL"], api_key=os.environ["LITELLM_API_KEY"])
)
session = f"smoke-{uuid.uuid4().hex[:8]}"


@neatlogs.span(kind="WORKFLOW")
def smoke():
    r = client.chat.completions.create(
        model="claude-haiku", messages=[{"role": "user", "content": "Say 'Agent Doctor online' and nothing else."}]
    )
    return r.choices[0].message.content


with neatlogs.trace("smoke-test", session_id=session):
    print("LLM:", smoke())
neatlogs.flush()

time.sleep(5)
resp = httpx.get(
    "https://app.neatlogs.com/api/v1/public/traces",
    headers={"x-api-key": os.environ["NEATLOGS_API_KEY"]},
    params={"sessionId": session, "limit": 5},
)
print("API status:", resp.status_code)
print(resp.text[:1500])
