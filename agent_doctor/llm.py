"""Shared LLM client: OpenAI-compatible LiteLLM endpoint, traced by neatlogs."""
import os
from pathlib import Path

import neatlogs
from dotenv import load_dotenv
from neatlogs.openai import wrap_openai_client
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

PATIENT_MODEL = os.getenv("PATIENT_MODEL", "claude-haiku")
DOCTOR_MODEL = os.getenv("DOCTOR_MODEL", "claude-sonnet-4.6")

_client = None


def get_client() -> OpenAI:
    """Init neatlogs once and return a traced OpenAI client pointed at LiteLLM."""
    global _client
    if _client is None:
        neatlogs.init(api_key=os.environ["NEATLOGS_API_KEY"])
        _client = wrap_openai_client(
            OpenAI(base_url=os.environ["LITELLM_BASE_URL"], api_key=os.environ["LITELLM_API_KEY"])
        )
    return _client
