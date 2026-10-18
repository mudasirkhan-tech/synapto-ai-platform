# Files changed since the Phase 4 package

## Added (29)
- `apps/api/alembic/versions/0004_agent_tasks.py`
- `apps/api/alembic/versions/0005_providers.py`
- `apps/api/app/providers/__init__.py`
- `apps/api/app/providers/base.py`
- `apps/api/app/providers/deepseek.py`
- `apps/api/app/providers/gemini.py`
- `apps/api/app/providers/ollama.py`
- `apps/api/app/routers/agent.py`
- `apps/api/app/routers/providers.py`
- `apps/api/app/services/agent.py`
- `apps/api/app/services/agent_tools.py`
- `apps/api/app/services/catalog.py`
- `apps/api/app/services/chat_agent.py`
- `apps/api/app/services/credentials.py`
- `apps/api/app/services/limiter.py`
- `apps/api/app/services/routing.py`
- `apps/api/app/services/titles.py`
- `apps/api/tests/fakes.py`
- `apps/api/tests/test_agent.py`
- `apps/api/tests/test_cloud_chat.py`
- `apps/api/tests/test_credentials.py`
- `apps/api/tests/test_providers.py`
- `apps/api/tests/test_routing.py`
- `apps/web/components/views/AgentPanel.tsx`
- `apps/web/components/views/ApiKeyCard.tsx`
- `apps/web/lib/languages.ts`
- `apps/web/lib/useSpeechRecognition.ts`
- `apps/web/lib/useSpeechSynthesis.ts`
- `apps/web/lib/views.ts`

## Modified (32)
- `.gitignore`
- `apps/api/.env.example`
- `apps/api/app/config.py`
- `apps/api/app/main.py`
- `apps/api/app/models.py`
- `apps/api/app/routers/auth.py`
- `apps/api/app/routers/chat.py`
- `apps/api/app/routers/conversations.py`
- `apps/api/app/routers/models.py`
- `apps/api/app/schemas.py`
- `apps/api/app/services/llm.py`
- `apps/api/app/services/prompt.py`
- `apps/api/pyproject.toml`
- `apps/api/tests/conftest.py`
- `apps/api/tests/test_phase3.py`
- `apps/web/components/Capabilities.tsx`
- `apps/web/components/ChatMessages.tsx`
- `apps/web/components/Composer.tsx`
- `apps/web/components/Header.tsx`
- `apps/web/components/Hero.tsx`
- `apps/web/components/LocalStatusCard.tsx`
- `apps/web/components/ModelSelector.tsx`
- `apps/web/components/Sidebar.tsx`
- `apps/web/components/Workspace.tsx`
- `apps/web/components/views/CodeView.tsx`
- `apps/web/components/views/SettingsView.tsx`
- `apps/web/components/views/ToolsView.tsx`
- `apps/web/components/views/VoiceView.tsx`
- `apps/web/lib/api.ts`
- `apps/web/lib/chat.ts`
- `apps/web/lib/prefs.ts`
- `apps/web/lib/useModels.ts`

## Deleted (0)
