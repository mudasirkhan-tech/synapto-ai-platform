"""Tool registry for the agent. Every tool has a validated argument schema, a timeout, and an approval policy."""
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select

from app import db as dbmod
from app.config import Settings
from app.models import Document
from app.services import embeddings, retrieval, tools
from app.services.ingest import ingest_document
from app.services.search import web_search


@dataclass
class ToolContext:
    user_id: str
    settings: Settings


class CalcArgs(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


class ConvertArgs(BaseModel):
    value: float
    from_unit: str = Field(max_length=10)
    to_unit: str = Field(max_length=10)


class QueryArgs(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class NoArgs(BaseModel):
    pass


class NoteArgs(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=20000)


@dataclass
class Tool:
    name: str
    description: str
    params: str                      # human-readable signature shown to the model
    args_model: type[BaseModel]
    run: Callable[[ToolContext, BaseModel], Awaitable[str]]
    requires_approval: bool = False  # side effects must be confirmed by the user first
    timeout_s: float | None = None
    needs: str | None = None         # "knowledge" | "web": only offered when enabled for the task


async def _calculator(ctx: ToolContext, a: CalcArgs) -> str:
    return str(tools.evaluate(a.expression))


async def _convert(ctx: ToolContext, a: ConvertArgs) -> str:
    return str(round(tools.convert(a.value, a.from_unit, a.to_unit), 10))


async def _datetime(ctx: ToolContext, a: NoArgs) -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


async def _search_documents(ctx: ToolContext, a: QueryArgs) -> str:
    with dbmod.SessionLocal() as db:
        ids = list(
            db.scalars(
                select(Document.id).where(
                    Document.user_id == ctx.user_id, Document.scope == "library",
                    Document.kind == "document", Document.status == "ready",
                )
            )
        )
        if not ids:
            return "The user's document library has no ready documents."
        vec = None
        try:
            vecs = await run_in_threadpool(embeddings.embed_texts, ctx.settings.ollama_url, ctx.settings.embed_model, [a.query])
            vec = embeddings.normalise(vecs[0])
        except embeddings.EmbedError:
            pass
        hits = retrieval.retrieve(db, ctx.user_id, ids, a.query, vec, k=ctx.settings.retrieval_top_k, small_doc_chars=0)
    if not hits:
        return "No matching passages were found."
    return "\n\n".join(
        f"[{i}] {h.filename}{f' (page {h.page})' if h.page else ''}: {h.text[:700]}" for i, h in enumerate(hits, start=1)
    )


async def _web_search(ctx: ToolContext, a: QueryArgs) -> str:
    results = await web_search(ctx.settings.searxng_url or "", a.query, limit=5)
    if not results:
        return "No web results."
    return "\n".join(f"- {r.title} ({r.url}): {r.snippet}" for r in results)


async def _save_note(ctx: ToolContext, a: NoteArgs) -> str:
    name = (re.sub(r"[^\w\- ]+", "", a.title).strip()[:80] or "note") + ".md"
    data = a.content.encode()
    with dbmod.SessionLocal() as db:
        doc = Document(user_id=ctx.user_id, scope="library", kind="document", filename=name,
                       mime="text/markdown", size_bytes=len(data), status="processing")
        db.add(doc)
        db.commit()
        doc_id = doc.id
    await run_in_threadpool(ingest_document, doc_id, name, data, ctx.settings)
    return f"Saved '{name}' to the user's document library."


ALL_TOOLS: list[Tool] = [
    Tool("calculator", "Evaluate a math expression exactly (use instead of mental arithmetic).",
         "expression: string", CalcArgs, _calculator),
    Tool("convert_units", "Convert between units of length, mass, volume, time, data or temperature (c, f, k).",
         "value: number, from_unit: string, to_unit: string", ConvertArgs, _convert),
    Tool("current_datetime", "Get the current local date and time.", "no arguments", NoArgs, _datetime),
    Tool("search_documents", "Search the user's private document library for relevant passages.",
         "query: string", QueryArgs, _search_documents, needs="knowledge"),
    Tool("web_search", "Search the web for current information.", "query: string", QueryArgs, _web_search, needs="web"),
    Tool("save_note", "Save a Markdown note to the user's document library. Changes their data, so it needs approval.",
         "title: string, content: string", NoteArgs, _save_note, requires_approval=True, timeout_s=60.0),
]


def _enabled(tool: Tool, settings: Settings, use_knowledge: bool, web: bool) -> bool:
    if tool.needs == "knowledge":
        return use_knowledge
    if tool.needs == "web":
        return web and bool(settings.searxng_url)
    return True


def available_tools(settings: Settings, use_knowledge: bool, web: bool) -> dict[str, Tool]:
    return {t.name: t for t in ALL_TOOLS if _enabled(t, settings, use_knowledge, web)}


def catalog(settings: Settings) -> list[dict]:
    out = []
    for t in ALL_TOOLS:
        available = bool(settings.searxng_url) if t.needs == "web" else True
        note = ""
        if t.needs == "web" and not available:
            note = "Needs SYNAPTO_SEARXNG_URL"
        elif t.needs:
            note = "Enable it for the task to use it"
        out.append({"name": t.name, "description": t.description, "requires_approval": t.requires_approval,
                    "available": available, "note": note})
    return out
