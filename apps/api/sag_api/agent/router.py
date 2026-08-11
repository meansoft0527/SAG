"""Agent REST 接口扩展。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sag_api.agent.orchestrator import AgentOrchestrator

router = APIRouter(prefix="/agent-ext", tags=["agent-ext"])
orchestrator = AgentOrchestrator()


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/chat")
async def agent_chat(req: AgentChatRequest, request: Request):
    """扩展智能体对话入口（支持 Skill 优先与通用编排）。"""
    llm = getattr(request.app.state, "llm", None)

    async def event_stream():
        async for chunk in orchestrator.run(req.message, conversation_id=req.conversation_id, llm=llm):
            yield chunk

    return StreamingResponse(event_stream(), media_type="text/plain")
