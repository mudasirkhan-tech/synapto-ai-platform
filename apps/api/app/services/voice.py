"""Optional local speech-to-text with faster-whisper (install: uv sync --extra voice)."""
import importlib.util
import io
import threading

_model = None
_lock = threading.Lock()


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def transcribe(data: bytes, model_name: str, language: str | None) -> tuple[str, str | None]:
    global _model
    from faster_whisper import WhisperModel  # imported lazily: optional dependency

    with _lock:  # one shared model instance; transcriptions are serialised
        if _model is None:
            _model = WhisperModel(model_name, device="auto", compute_type="int8")
        segments, info = _model.transcribe(io.BytesIO(data), language=language or None, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
    return text, getattr(info, "language", None)
