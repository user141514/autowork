from fastapi import APIRouter

from app.api.agent_runs import router as agent_runs_router
from app.api.bot import router as bot_router
from app.api.chat_feedback import router as chat_feedback_router
from app.api.context_confidence import router as context_confidence_router
from app.api.dashboard import router as dashboard_router
from app.api.demand_radar import router as demand_radar_router
from app.api.git_ops import router as git_ops_router
from app.api.llm import router as llm_router
from app.api.message_documents import router as message_documents_router
from app.api.messages import router as messages_router
from app.api.policy_decisions import router as policy_decisions_router
from app.api.reports import router as reports_router
from app.api.requirement_promotion import router as requirement_promotion_router
from app.api.review_workbench import router as review_workbench_router
from app.api.segments import router as segments_router
from app.api.tests import router as tests_router
from app.api.task_candidates import router as task_candidates_router
from app.api.wechat import router as wechat_router
from app.api.wechat_directory import router as wechat_directory_router
from app.api.workdocs import router as workdocs_router
from app.config import get_settings


router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, bool | str]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "dry_run": settings.dry_run,
    }


router.include_router(dashboard_router)
router.include_router(demand_radar_router)
router.include_router(requirement_promotion_router)
router.include_router(review_workbench_router)
router.include_router(llm_router)
router.include_router(message_documents_router)
router.include_router(messages_router)
router.include_router(bot_router)
router.include_router(segments_router)
router.include_router(task_candidates_router)
router.include_router(workdocs_router)
router.include_router(agent_runs_router)
router.include_router(git_ops_router)
router.include_router(policy_decisions_router)
router.include_router(tests_router)
router.include_router(reports_router)
router.include_router(wechat_router)
router.include_router(wechat_directory_router)
router.include_router(chat_feedback_router)
router.include_router(context_confidence_router)
