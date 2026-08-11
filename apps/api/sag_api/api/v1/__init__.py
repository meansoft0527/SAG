from fastapi import APIRouter

from sag_api.agent.router import router as agent_ext_router
from sag_api.api.v1 import (
    activity,
    agents,
    attachments,
    auth,
    dify,
    documents,
    insights,
    jobs,
    knowledge,
    openai,
    search,
    sources,
    system,
    universe,
)
from sag_api.connectors_ext.router import router as connectors_ext_router
from sag_api.skills.router import router as skills_router
from sag_api.wiki.router import router as wiki_router

api_router = APIRouter(prefix="/api/v1")
for _module in (
    auth,
    dify,
    sources,
    documents,
    insights,
    knowledge,
    jobs,
    search,
    agents,
    openai,
    activity,
    attachments,
    system,
    universe,
):
    api_router.include_router(_module.router)

api_router.include_router(skills_router)
api_router.include_router(wiki_router)
api_router.include_router(agent_ext_router)
api_router.include_router(connectors_ext_router)
api_router.include_router(search.global_router)



__all__ = ["api_router"]
