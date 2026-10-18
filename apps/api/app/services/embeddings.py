"""Local embeddings through Ollama's /api/embed."""
import httpx
import numpy as np


class EmbedError(Exception):
    """User-presentable embedding failure."""


def embed_texts(base_url: str, model: str, texts: list[str], timeout: float = 120.0) -> list[list[float]]:
    out: list[list[float]] = []
    try:
        with httpx.Client(base_url=base_url, timeout=timeout) as client:
            for i in range(0, len(texts), 16):
                res = client.post("/api/embed", json={"model": model, "input": texts[i : i + 16], "keep_alive": "10m"})
                if res.status_code == 404:
                    raise EmbedError(f"Embedding model '{model}' is not installed. Run: ollama pull {model}")
                res.raise_for_status()
                out.extend(res.json()["embeddings"])
    except httpx.ConnectError as exc:
        raise EmbedError(f"Cannot reach Ollama at {base_url}.") from exc
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        raise EmbedError("The embedding request failed.") from exc
    if len(out) != len(texts):
        raise EmbedError("The embedding model returned an unexpected number of vectors.")
    return out


def normalise(vec: list[float] | np.ndarray) -> np.ndarray:
    arr = np.asarray(vec, dtype=np.float32)
    norm = float(np.linalg.norm(arr))
    return arr / norm if norm else arr


def to_blob(vec: list[float]) -> bytes:
    return normalise(vec).tobytes()
