# SYNAPTO — Phase 5 (cloud-first, voice, agents)

Cloud models answer by default; Ollama stays available as the last-priority fallback. See `CHANGES.md` for every file added or modified since the Phase 4 package.

## 1. Install and run

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), Node 20+, pnpm.

```bash
# API (terminal 1)
cd apps/api
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
uv sync
uv run alembic upgrade head     # additive migrations 0004 (agent tasks) and 0005 (provider keys, message provider/finish)
uv run pytest
uv run uvicorn app.main:app --reload --port 8000

# Web (terminal 2)
cd apps/web
cp .env.example .env.local
pnpm install
pnpm dev                        # http://localhost:3000
```

## 2. API keys (pick one way)
1. **In the app (per user):** Settings → API keys → paste, **Save**, **Test connection**. Stored encrypted (Fernet) on the server; never sent back to the browser; only the last 4 characters are shown.
2. **Server-wide environment variables** (`apps/api/.env`, which is git-ignored): `DEEPSEEK_API_KEY=...` and `GEMINI_API_KEY=...`. A user's own key wins over the server key.

Local single-user note: if `SYNAPTO_ENCRYPTION_KEY` is unset, a master key is created once at `apps/api/data/.secret_key` (mode 600) and never overwritten. Anyone who can read that file and the database can decrypt stored keys, so for shared deployments use environment keys or set `SYNAPTO_ENCRYPTION_KEY` from a secrets manager.

## 3. Model IDs (verified 2026-10-13)
The IDs in your brief have been retired, so the defaults are the provider-documented replacements. All are configurable in `.env`, and the model selector shows whether each ID is actually offered to your key.

| Slot | You asked for | Status | Default now |
|---|---|---|---|
| DeepSeek Chat | `deepseek-chat` | retired 2026-07-24 | `deepseek-flash` (thinking off) |
| DeepSeek Reasoner | `deepseek-reasoner` | retired 2026-07-24 | `deepseek-flash` (thinking on); `deepseek-v4-pro` is the stronger option |
| Gemini Pro | `gemini-1.5-pro` | shut down | `gemini-3.1-pro-preview` |
| Gemini Flash | `gemini-2.0-flash` | shut down (2026-06-01) | `gemini-3.5-flash` |

**Routing** (`Auto`): DeepSeek Chat → Gemini Pro → Gemini Flash → Ollama. Only providers with a key are tried. Auto picks DeepSeek Reasoner first for clearly hard maths/logic prompts (`SYNAPTO_ROUTE_REASONING`). A manual choice always goes first.
**Fallback** happens only before any text was produced and only for rate limits, timeouts and outages (plus missing/rejected keys in Auto). One retry per provider, no infinite loops. A failure mid-answer is reported, not silently replaced. A switch to local Ollama is announced as slow. Toggle in Settings.

## 4. Streaming events (`POST /api/v1/chat/stream`, `/chat/regenerate`)
Additive: old clients that only know `meta/token/error/done` keep working.

| Event | Payload | Meaning |
|---|---|---|
| `meta` | conversation_id, user_message_id | stream opened |
| `sources` | sources[] | citations (documents/web) |
| `status` | phase, message, provider?, model?, label? | connecting, thinking, retry, processing, info |
| `fallback` | from, to, reason, slow, message | provider switched before any text |
| `tool_start` / `tool_result` | n, tool, args / ok, preview | a tool really ran (server-emitted) |
| `token` | text, seq | incremental text; `seq` strictly increases (client drops duplicates) |
| `error` | message | failure, secrets redacted |
| `done` | message_id, finish (`complete`/`stopped`/`error`), provider, model, latency_ms, first_token_ms, usage | partial replies are saved flagged incomplete |
| `title` | conversation_id, title | after `done`, new chats only |

Chat tool use (wrench button) offers only read-only tools. Anything that changes data runs in Tools → Agent workflows, which asks for approval first.

## 5. Voice
Dictation uses the browser's Web Speech API (feature-detected; one session at a time; the transcript goes into the editable input, never auto-sent). Whether audio stays on-device depends on the browser; Chrome/Edge typically use a cloud service. Local Whisper (`uv sync --extra voice`) is only used where the browser has none, or for uploaded audio. Replies can be read aloud with the browser's SpeechSynthesis (voice picker, pause/resume/stop, chunked, cancelled on navigation).

## 6. Tests
`uv run pytest` runs about 80 tests with mocked providers (DeepSeek through `httpx.MockTransport`, Gemini through an injected fake client, fake providers for routing). No test needs a real key. See the delivery report for which of them were actually executed.

## 7. Production checklist (not done by this code)
HTTPS and a reverse proxy; a strong `SYNAPTO_JWT_SECRET` (the API refuses to start without one outside development); httpOnly cookies instead of the browser-stored login token; shared rate limiting (the built-in limiter is per process); log shipping and monitoring; database backups; moving off SQLite for multi-user use; a vector database for large libraries; CSRF protection if you move to cookie auth; provider spending limits.
