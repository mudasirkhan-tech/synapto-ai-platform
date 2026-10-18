import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import AgentStep, AgentTask, User, utcnow
from app.schemas import AgentStepOut, AgentTaskIn, AgentTaskOut, DecisionIn, ToolInfo
from app.services import routing
from app.services.agent import TERMINAL, add_step, run_agent
from app.services.agent_tools import catalog

router = APIRouter(prefix="/agent", tags=["agent"])


def _out(task: AgentTask, with_steps: bool) -> AgentTaskOut:
    steps = [
        AgentStepOut(id=s.id, idx=s.idx, kind=s.kind, tool=s.tool, args=json.loads(s.args_json) if s.args_json else None,
                     content=s.content, status=s.status, created_at=s.created_at)
        for s in task.steps
    ] if with_steps else []
    return AgentTaskOut(id=task.id, goal=task.goal, status=task.status, model=task.model, use_knowledge=task.use_knowledge,
                        web_search=task.web_search, final_answer=task.final_answer, error=task.error,
                        created_at=task.created_at, updated_at=task.updated_at, steps=steps)


def owned_task(db: Session, user: User, task_id: str) -> AgentTask:
    task = db.scalar(
        select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user.id).options(selectinload(AgentTask.steps))
    )
    if task is None:
        raise HTTPException(404, "Task not found")
    return task


@router.get("/tools", response_model=list[ToolInfo])
def list_tools(_: User = Depends(get_current_user), settings: Settings = Depends(get_settings)):
    return catalog(settings)


@router.post("/tasks", response_model=AgentTaskOut)
def create_task(
    body: AgentTaskIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if body.web_search and not settings.searxng_url:
        raise HTTPException(501, "Web search isn't configured. Set SYNAPTO_SEARXNG_URL (see README).")
    try:
        routing.parse_selection(body.model, settings)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    task = AgentTask(user_id=user.id, goal=body.goal.strip(), model=body.model or "auto",
                     use_knowledge=body.use_knowledge, web_search=body.web_search)
    db.add(task)
    db.flush()
    add_step(db, task.id, "info", content="Task created")
    db.commit()
    background.add_task(run_agent, task.id, settings)
    return _out(owned_task(db, user, task.id), True)


@router.get("/tasks", response_model=list[AgentTaskOut])
def list_tasks(limit: int = Query(30, ge=1, le=100), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(AgentTask).where(AgentTask.user_id == user.id).order_by(AgentTask.created_at.desc()).limit(limit)
    return [_out(t, False) for t in db.scalars(stmt)]


@router.get("/tasks/{task_id}", response_model=AgentTaskOut)
def get_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _out(owned_task(db, user, task_id), True)


@router.post("/tasks/{task_id}/cancel", response_model=AgentTaskOut)
def cancel(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    if task.status not in TERMINAL:
        task.status = "cancelled"
        task.updated_at = utcnow()
        add_step(db, task.id, "info", content="Cancelled by the user")
        db.commit()
        db.refresh(task)
    return _out(owned_task(db, user, task_id), True)


@router.post("/tasks/{task_id}/decision", response_model=AgentTaskOut)
def decide(
    task_id: str,
    body: DecisionIn,
    background: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    task = owned_task(db, user, task_id)
    if task.status != "waiting_approval":
        raise HTTPException(409, "This task is not waiting for approval")
    step = db.scalar(
        select(AgentStep).where(AgentStep.task_id == task.id, AgentStep.status == "pending_approval").order_by(AgentStep.idx.desc())
    )
    if step is None:
        raise HTTPException(409, "No action is waiting for approval")
    if body.approve:
        step.status = "approved"
    else:
        step.status = "denied"
        add_step(db, task.id, "tool_result", tool=step.tool,
                 content="The user denied this action. Continue without it and say so in your answer.")
    task.status = "running"  # claim the task so a repeated click gets a 409
    task.updated_at = utcnow()
    db.commit()
    background.add_task(run_agent, task.id, settings)
    return _out(owned_task(db, user, task_id), True)


@router.delete("/tasks/{task_id}", status_code=204, response_class=Response)
def delete_task(task_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = owned_task(db, user, task_id)
    if task.status not in TERMINAL and task.status != "waiting_approval":
        raise HTTPException(409, "Cancel the task before deleting it")
    db.delete(task)
    db.commit()
    return Response(status_code=204)
