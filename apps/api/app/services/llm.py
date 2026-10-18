"""Streaming chat against a local Ollama server."""
import json
from collections.abc import AsyncIterator

import httpx


class LLMError(Exception):
    """A user-presentable model/runtime failure."""


async def stream_chat(
    base_url: str, model: str, messages: list[dict], num_ctx: int
) -> AsyncIterator[str]:
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "keep_alive": "10m",
        "options": {"num_ctx": num_ctx},
    }
    timeout = httpx.Timeout(10.0, read=120.0)  # generous read: first call loads the model
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            async with client.stream("POST", "/api/chat", json=payload) as res:
                if res.status_code == 404:
                    raise LLMError(f"Model '{model}' is not installed. Run: ollama pull {model}")
                if res.status_code >= 400:
                    raise LLMError(f"Ollama returned HTTP {res.status_code}")
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LLMError(str(chunk["error"]))
                    text = chunk.get("message", {}).get("content", "")
                    if text:
                        yield text
                    if chunk.get("done"):
                        break
    except httpx.ConnectError as exc:
        raise LLMError(f"Cannot reach Ollama at {base_url}. Is `ollama serve` running?") from exc
    except httpx.TimeoutException as exc:
        raise LLMError("The model took too long to respond.") from exc
    except httpx.HTTPError as exc:
        raise LLMError("Connection to Ollama failed.") from exc
    except ValueError as exc:
        raise LLMError("Received an unreadable response from Ollama.") from exc


def clean_title(raw: str) -> str | None:
    """Normalise a model-written title: one line, no quotes/markdown, no trailing punctuation."""
    lines = raw.strip().splitlines()
    line = lines[0].strip() if lines else ""
    if line.lower().startswith("title:"):
        line = line[6:]
    line = line.strip().strip("\"'`*#").strip().rstrip(".!?:;,").strip()
    line = " ".join(line.split())
    return line[:60] if line else None


async def generate_title(base_url: str, model: str, first_message: str) -> str | None:
    """Ask the local model for a 3-6 word title. Returns None on any failure (caller keeps its fallback)."""
    prompt = (
        "Write a short title (3 to 6 words) for a chat that begins with the message below. "
        "Reply with only the title: no quotes, no trailing punctuation.\n\n"
        f"Message:\n{first_message[:600]}"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": "10m",
        "options": {"num_predict": 24, "temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=20.0) as client:
            res = await client.post("/api/generate", json=payload)
            res.raise_for_status()
            return clean_title(res.json().get("response", ""))
    except (httpx.HTTPError, ValueError):
        return None


async def chat_json(base_url: str, model: str, messages: list[dict], num_ctx: int, timeout: float = 90.0) -> str:
    """One non-streaming chat turn with Ollama's JSON mode. Used by the agent for structured decisions."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "format": "json",
        "keep_alive": "10m",
        "options": {"num_ctx": num_ctx, "temperature": 0.2},
    }
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
            res = await client.post("/api/chat", json=payload)
            if res.status_code == 404:
                raise LLMError(f"Model '{model}' is not installed. Run: ollama pull {model}")
            res.raise_for_status()
            return str(res.json()["message"]["content"])
    except httpx.ConnectError as exc:
        raise LLMError(f"Cannot reach Ollama at {base_url}. Is `ollama serve` running?") from exc
    except httpx.TimeoutException as exc:
        raise LLMError("The model took too long to respond.") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise LLMError("Ollama returned an unusable response.") from exc
