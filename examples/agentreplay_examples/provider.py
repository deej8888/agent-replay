"""Optional real adapter. The demo never imports or invokes this module."""
import os

import httpx
from agentreplay import trace_llm


@trace_llm(name="openai-completion", model="provider-configured")
def provider_completion(prompt: str) -> str:
    key = os.environ["OPENAI_API_KEY"]
    model = os.environ["OPENAI_MODEL"]
    response = httpx.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {key}"}, json={"model": model, "input": prompt}, timeout=30)
    response.raise_for_status()
    for item in response.json()["output"]:
        if item.get("type") == "message":
            for content in item["content"]:
                if content.get("type") == "output_text":
                    return str(content["text"])
    raise ValueError("Provider returned no text")
