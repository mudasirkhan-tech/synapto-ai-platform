"""Chat streaming over SSE.

Events (all `event: <name>` + JSON `data:`; additive, so older clients that only know meta/token/error/done still work):
  meta        {conversation_id, user_message_id}
  sources     {sources: [...]}                              document / web citations used for this answer
  status      {phase, message, provider?, model?, label?}   connecting | thinking | retry | tool | processing | info
  fallback    {from, to, reason, slow, message}             provider switch before any text was produced
  tool_start  {n, tool, args, message}                      a tool is really being executed
  tool_result {n, tool, ok, preview}
  token       {text, seq}                                   incremental answer text; seq is strictly increasing
  error       {message}
  done        {message_id, finish, provider, model, label, latency_ms, first_token_ms, usage}
              finish = complete | stopped | error (partial text is saved, flagged incomplete)
  title       {conversation_id, title}                      after done, for new conversations
"""
import asyncio
import contextlib
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db as dbmod
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import Conversation, Document, Message, User, utcnow
from app.routers.conversations import owned_conversation
from app.schemas import ChatIn, RegenerateIn, WebResult
from app.services import credentials, routing, runtime, titles
from app.services.agent_tools import available_tools
from app.services.chat_agent import run_chat_agent
from app.services.context import TurnContext, build_context
from app.services.prompt import build_messages
from app.services.search import SearchError, web_search

router = APIRouter(tags=["chat"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _fallback_title(text: str) -> str:
    one_line = " ".join(text.split())
    return (one_line[:50] + "…") if len(one_line) > 50 else one_line or "New chat"


def _save_assistant(conversation_id: str, text: str, model: str, provider: str, finish: str, sources: list[dict]) -> int | None:
    if not text:
        return None
    with dbmod.SessionLocal() as s:
        msg = Message(
            conversation_id=conversation_id, role="assistant", content=text, model=model, provider=provider or None,
            finish=finish, sources_json=json.dumps(sources) if sources else None,
        )
        s.add(msg)
        conv = s.get(Conversation, conversation_id)
        if conv is not None:
            conv.updated_at = utcnow()
        s.commit()
        return msg.id


def _set_title(conversation_id: str, title: str) -> None:
    with dbmod.SessionLocal() as s:
        conv = s.get(Conversation, conversation_id)
        if conv is not None:
            conv.title = title
            s.commit()


async def _web_results(enabled: bool, query: str, settings: Settings) -> list[WebResult]:
    if not enabled:
        return []
    if not settings.searxng_url:
        raise HTTPException(501, "Web search isn't configured. Set SYNAPTO_SEARXNG_URL (see README).")
    try:
        return await web_search(settings.searxng_url, query)
    except SearchError as exc:
        raise HTTPException(502, str(exc)) from exc


async def _make_plan(
    db: Session, user: User, model: str | None, settings: Settings, *, query: str, has_images: bool, fallback: bool | None
) -> tuple[routing.RoutePlan, dict[str, str]]:
    keys = credentials.resolve_keys(db, user.id, settings)
    try:
        selection = routing.parse_selection(model, settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if has_images and selection.spec is not None and selection.spec.vision is False:
        raise HTTPException(422, f"{selection.spec.label} can't read images. Choose Auto, Gemini, or a local vision model.")
    plan = routing.build_plan(selection, settings, keys, query=query, needs_vision=has_images, fallback=fallback)
    if has_images:
        kept = []
        for spec in plan.candidates:
            if spec.provider == "ollama":
                caps = await runtime.get_capabilities(settings.ollama_url, spec.model)
                if caps is not None and "vision" not in caps:
                    if not selection.auto and spec.ref == selection.spec.ref:  # type: ignore[union-attr]
                        raise HTTPException(422, f"'{spec.model}' can't read images. Pick a vision model, e.g. `ollama pull llama3.2-vision`.")
                    continue
            kept.append(spec)
        plan.candidates = kept
        if not kept:
            raise HTTPException(422, "No available model can read images. Pick a vision model (for example Gemini, or `ollama pull llama3.2-vision`).")
    return plan, keys


async def _events(*, conversation_id, user_message_id, prompt, plan, keys, settings, title_source, sources, tool_cfg):
    parts: list[str] = []
    error: str | None = None
    info: dict = {}
    used: dict = {}
    seq = 0
    stopped = False
    yield _sse("meta", {"conversation_id": conversation_id, "user_message_id": user_message_id})
    if sources:
        yield _sse("sources", {"sources": sources})
    for note in plan.notes:
        yield _sse("status", {"phase": "info", "message": note})

    if tool_cfg:
        stream = run_chat_agent(plan, prompt, settings=settings, keys=keys, tools=tool_cfg[0], user_id=tool_cfg[1])
    else:
        stream = routing.route_stream(plan, prompt, settings=settings, keys=keys)
    try:
        async for ev in stream:
            kind = ev["type"]
            if kind == "token":
                parts.append(ev["text"])
                seq += 1
                yield _sse("token", {"text": ev["text"], "seq": seq})
            elif kind == "finished":
                info = ev
            elif kind == "error":
                error = ev["message"]
            else:
                if kind == "status" and ev.get("provider"):
                    used = {"provider": ev["provider"], "model": ev["model"], "label": ev["label"]}
                yield _sse(kind, {k: v for k, v in ev.items() if k != "type"})
    except (asyncio.CancelledError, GeneratorExit):
        stopped = True  # client pressed Stop or disconnected
        raise
    finally:
        with contextlib.suppress(Exception):
            await stream.aclose()
        finish = "stopped" if stopped else ("error" if error else "complete")
        who = info or used
        message_id = _save_assistant(conversation_id, "".join(parts), who.get("model", ""), who.get("provider", ""), finish, sources)
    if error:
        yield _sse("error", {"message": error})
    yield _sse("done", {
        "message_id": message_id, "finish": finish, "provider": who.get("provider"), "model": who.get("model"),
        "label": who.get("label"), "latency_ms": info.get("latency_ms"), "first_token_ms": info.get("first_token_ms"),
        "usage": info.get("usage"),
    })

    if title_source and message_id is not None and error is None and who.get("provider"):
        title = await titles.generate(settings, keys, title_source, who["provider"], who["model"])
        if title:
            _set_title(conversation_id, title)
            yield _sse("title", {"conversation_id": conversation_id, "title": title})


def _response(gen) -> StreamingResponse:
    return StreamingResponse(gen, media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _tool_cfg(body, settings: Settings, user: User):
    if not body.tools:
        return None
    if body.web_search and not settings.searxng_url:
        raise HTTPException(501, "Web search isn't configured. Set SYNAPTO_SEARXNG_URL (see README).")
    # Chat only offers read-only tools; tools that change data need the approval flow in Agent tasks.
    tools = {n: t for n, t in available_tools(settings, body.use_knowledge, body.web_search).items() if not t.requires_approval}
    return tools, user.id


@router.post("/chat/stream")
async def chat_stream(
    body: ChatIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    tool_cfg = _tool_cfg(body, settings, user)
    web = [] if tool_cfg else await _web_results(body.web_search, body.message, settings)  # before any DB writes

    docs: list[Document] = []
    if body.document_ids:
        docs = list(
            db.scalars(
                select(Document).where(
                    Document.id.in_(body.document_ids), Document.user_id == user.id,
                    Document.scope == "chat", Document.message_id.is_(None),
                )
            )
        )
        if len(docs) != len(set(body.document_ids)):
            raise HTTPException(404, "One or more attachments were not found")
        if any(d.status == "processing" for d in docs):
            raise HTTPException(409, "A file is still being processed. Try again in a moment.")
        if any(d.status == "failed" for d in docs):
            raise HTTPException(422, "A file failed to process. Remove it and try again.")

    plan, keys = await _make_plan(db, user, body.model, settings, query=body.message,
                                  has_images=any(d.kind == "image" for d in docs), fallback=body.fallback)

    is_new = body.conversation_id is None
    if is_new:
        conv = Conversation(user_id=user.id, title=_fallback_title(body.message))
        db.add(conv)
        db.flush()
    else:
        conv = owned_conversation(db, user, body.conversation_id)

    user_msg = Message(conversation_id=conv.id, role="user", content=body.message)
    db.add(user_msg)
    db.flush()
    for d in docs:
        d.message_id = user_msg.id
    conv.updated_at = utcnow()
    db.commit()

    ctx: TurnContext = await build_context(
        db, user_id=user.id, conversation_id=conv.id, query=body.message,
        use_knowledge=body.use_knowledge and not tool_cfg, web_results=web, settings=settings,
    )
    return _response(
        _events(
            conversation_id=conv.id, user_message_id=user_msg.id, prompt=build_messages(db, conv.id, settings, ctx.block),
            plan=plan, keys=keys, settings=settings, title_source=body.message if is_new else None,
            sources=ctx.sources, tool_cfg=tool_cfg,
        )
    )


@router.post("/chat/regenerate")
async def regenerate(
    body: RegenerateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    conv = owned_conversation(db, user, body.conversation_id)
    tool_cfg = _tool_cfg(body, settings, user)

    def last_message() -> Message | None:
        return db.scalar(select(Message).where(Message.conversation_id == conv.id).order_by(Message.id.desc()).limit(1))

    last = last_message()
    if last is not None and last.role == "assistant":
        db.delete(last)  # replace the previous answer
        db.flush()
        last = last_message()
    if last is None or last.role != "user":
        raise HTTPException(409, "Nothing to regenerate")

    web = [] if tool_cfg else await _web_results(body.web_search, last.content, settings)
    has_images = bool(db.scalar(select(Document.id).where(Document.message_id == last.id, Document.kind == "image").limit(1)))
    plan, keys = await _make_plan(db, user, body.model, settings, query=last.content, has_images=has_images, fallback=body.fallback)
    user_message_id, query = last.id, last.content
    conv.updated_at = utcnow()
    db.commit()

    ctx = await build_context(
        db, user_id=user.id, conversation_id=conv.id, query=query,
        use_knowledge=body.use_knowledge and not tool_cfg, web_results=web, settings=settings,
    )
    return _response(
        _events(
            conversation_id=conv.id, user_message_id=user_message_id, prompt=build_messages(db, conv.id, settings, ctx.block),
            plan=plan, keys=keys, settings=settings, title_source=None, sources=ctx.sources, tool_cfg=tool_cfg,
        )
    )
