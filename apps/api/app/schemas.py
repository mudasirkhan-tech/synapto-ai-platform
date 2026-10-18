from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

MODEL_NAME = r"^[A-Za-z0-9._:/\-]+$"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    display_name: str
    email: str | None
    is_guest: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=80)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    updated_at: datetime


class ConversationPatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class AttachmentRef(BaseModel):
    id: str
    filename: str
    kind: str  # "document" | "image"


class SourceOut(BaseModel):
    n: int
    title: str
    kind: str  # "document" | "web"
    document_id: str | None = None
    page: int | None = None
    url: str | None = None
    snippet: str = ""


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    attachments: list[AttachmentRef]
    model: str | None = None
    provider: str | None = None
    finish: str | None = None
    sources: list[SourceOut] = []


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    filename: str
    kind: str
    scope: str
    status: str
    error: str | None
    chunk_count: int
    char_count: int
    embedded: bool
    size_bytes: int
    created_at: datetime


class ChatIn(BaseModel):
    conversation_id: str | None = None
    message: str = Field(min_length=1, max_length=8000)
    document_ids: list[str] = Field(default_factory=list, max_length=8)
    model: str | None = Field(default=None, max_length=100, pattern=MODEL_NAME)
    use_knowledge: bool = False  # also search the user's document library
    web_search: bool = False     # add live web results (requires SearXNG)
    tools: bool = False          # let the model call read-only tools (calculator, library/web search) with live progress
    fallback: bool | None = None  # None = server default


class RegenerateIn(BaseModel):
    conversation_id: str
    model: str | None = Field(default=None, max_length=100, pattern=MODEL_NAME)
    use_knowledge: bool = False
    web_search: bool = False
    tools: bool = False
    fallback: bool | None = None


class ModelEntry(BaseModel):
    name: str
    size_bytes: int | None = None
    tags: list[str] = []  # e.g. "vision", "multilingual", "code"


class CatalogModel(BaseModel):
    ref: str                 # what the client sends as `model`, e.g. "deepseek:chat" or "ollama:llama3.2:latest"
    label: str
    model_id: str
    state: str               # ready | unverified | needs_key | auth_error | billing | unavailable
    detail: str = ""
    tags: list[str] = []
    vision: bool | None = None


class CatalogGroup(BaseModel):
    id: str
    label: str
    cloud: bool
    status: str              # ok | no_key | auth_error | billing | unverified | unreachable
    detail: str = ""
    models: list[CatalogModel]


class AutoInfo(BaseModel):
    ref: str | None
    label: str
    order: list[str]
    note: str = ""


class ModelsOut(BaseModel):
    default: str                      # legacy: default Ollama model
    reachable: bool                   # legacy: Ollama reachable
    models: list[ModelEntry]          # legacy: Ollama models
    groups: list[CatalogGroup] = []
    auto: AutoInfo | None = None


class ProviderKeyIn(BaseModel):
    api_key: str = Field(min_length=8, max_length=300)


class ProviderTestIn(BaseModel):
    api_key: str | None = Field(default=None, max_length=300)


class ProviderOut(BaseModel):
    id: str
    label: str
    env_var: str
    configured: bool
    source: str | None = None        # "user" | "server"
    masked: str | None = None


class WebResult(BaseModel):
    title: str
    url: str
    snippet: str


class SearchIn(BaseModel):
    query: str = Field(min_length=1, max_length=300)


class ImageGenIn(BaseModel):
    prompt: str = Field(min_length=1, max_length=1000)
    negative_prompt: str = Field(default="", max_length=500)
    width: int = Field(default=512, ge=256, le=1024, multiple_of=8)
    height: int = Field(default=512, ge=256, le=1024, multiple_of=8)
    steps: int = Field(default=20, ge=1, le=50)


class CalcIn(BaseModel):
    expression: str = Field(min_length=1, max_length=200)


class ConvertIn(BaseModel):
    value: float
    from_unit: str = Field(max_length=10)
    to_unit: str = Field(max_length=10)


class AgentTaskIn(BaseModel):
    goal: str = Field(min_length=1, max_length=2000)
    model: str | None = Field(default=None, max_length=100, pattern=MODEL_NAME)
    use_knowledge: bool = False
    web_search: bool = False


class AgentStepOut(BaseModel):
    id: int
    idx: int
    kind: str
    tool: str | None = None
    args: dict | None = None
    content: str
    status: str
    created_at: datetime


class AgentTaskOut(BaseModel):
    id: str
    goal: str
    status: str
    model: str
    use_knowledge: bool
    web_search: bool
    final_answer: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStepOut] = []


class DecisionIn(BaseModel):
    approve: bool


class ToolInfo(BaseModel):
    name: str
    description: str
    requires_approval: bool
    available: bool
    note: str = ""
