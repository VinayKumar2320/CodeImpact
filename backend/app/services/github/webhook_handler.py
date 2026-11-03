from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.analysis import Analysis
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.schemas.github import GitHubWebhookPayload
from app.schemas.webhook import WebhookProcessingResult
from app.workers.queue import task_queue

logger = get_logger(__name__)


def run_pr_analysis_task(
    analysis_id: str,
    repo_full_name: str,
    head_sha: str,
    base_sha: str,
    diff_text: str | None = None,
    base_files: dict[str, str] | None = None,
    head_files: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Background job entrypoint invoked by RQ worker (or in-process runner during tests).
    Executes AST analysis, complexity delta extraction, and dependency graph construction.
    """
    from sqlalchemy.orm import Session

    from app.core.database import sync_engine
    from app.services.analysis.orchestrator import static_analysis_orchestrator

    logger.info(
        f"Background analysis task executing for analysis={analysis_id}, repo={repo_full_name}, sha={head_sha}"
    )

    analysis_res = static_analysis_orchestrator.analyze(
        diff_text=diff_text or "",
        base_files=base_files or {},
        head_files=head_files or {},
    )

    try:
        with Session(sync_engine) as session:
            stmt = select(Analysis).where(Analysis.id == analysis_id)
            analysis = session.execute(stmt).scalar_one_or_none()
            if analysis and analysis.status != "SUPERSEDED":
                analysis.status = "COMPLETED"
                analysis.features = analysis_res["features"]
                analysis.dependency_graph = analysis_res["dependency_graph"]
                analysis.execution_duration_ms = analysis_res["execution_duration_ms"]
                session.commit()
    except Exception as db_err:
        logger.warning(
            f"Could not persist analysis {analysis_id} via sync engine (ignorable in tests): {db_err}"
        )

    return {
        "analysis_id": analysis_id,
        "repo": repo_full_name,
        "head_sha": head_sha,
        "base_sha": base_sha,
        "status": "COMPLETED",
        "features": analysis_res["features"],
    }


class WebhookHandlerService:
    """
    Coordinates GitHub webhook processing, delivery deduplication via Redis,
    database state management, and analysis job dispatch.
    """

    def __init__(self, queue_manager=None):
        self.queue_manager = queue_manager or task_queue

    def check_and_record_delivery(self, delivery_id: str | None) -> bool:
        """
        Check if the delivery has already been processed using Redis SETNX.
        Returns True if the delivery is unique (new), False if it is a duplicate.
        """
        if not delivery_id:
            return True

        try:
            client = self.queue_manager.get_redis_client()
            dedupe_key = f"codeimpact:gh_delivery:{delivery_id}"
            # SETNX with 24 hour expiry (86400s)
            is_new = client.set(dedupe_key, "1", nx=True, ex=86400)
            return bool(is_new)
        except Exception as err:
            logger.warning(f"Redis delivery deduplication check bypassed due to Redis error: {err}")
            # In test mode or when redis is down, allow through
            return True

    async def handle_webhook(
        self,
        event: str,
        payload_data: dict,
        delivery_id: str | None,
        db: AsyncSession,
    ) -> WebhookProcessingResult:
        """
        Main ingress handler routing verified GitHub events.
        """
        # Deduplication check
        if delivery_id and not self.check_and_record_delivery(delivery_id):
            logger.info(f"Duplicate webhook delivery detected: {delivery_id}. Skipping.")
            return WebhookProcessingResult(
                status="duplicate",
                event=event,
                delivery_id=delivery_id,
                message=f"Duplicate delivery {delivery_id} ignored",
            )

        try:
            parsed = GitHubWebhookPayload.model_validate(payload_data)
        except Exception as val_err:
            logger.error(f"Failed to validate webhook payload: {val_err}")
            return WebhookProcessingResult(
                status="error",
                event=event,
                delivery_id=delivery_id,
                message=f"Invalid payload format: {val_err}",
            )

        if event == "pull_request":
            return await self._handle_pull_request_event(parsed, delivery_id, db)
        elif event == "installation":
            return await self._handle_installation_event(parsed, delivery_id, db)
        else:
            logger.info(f"Ignored unhandled GitHub event: {event}")
            return WebhookProcessingResult(
                status="ignored",
                event=event,
                action=parsed.action,
                delivery_id=delivery_id,
                message=f"Event {event} is not subscribed",
            )

    async def _handle_pull_request_event(
        self,
        payload: GitHubWebhookPayload,
        delivery_id: str | None,
        db: AsyncSession,
    ) -> WebhookProcessingResult:
        pr_payload = payload.pull_request
        repo_payload = payload.repository

        if not pr_payload or not repo_payload:
            return WebhookProcessingResult(
                status="error",
                event="pull_request",
                action=payload.action,
                delivery_id=delivery_id,
                message="Missing pull_request or repository payload",
            )

        action = payload.action.lower()
        logger.info(
            f"Processing pull_request.{action} for {repo_payload.full_name} PR #{pr_payload.number}"
        )

        # 1. Upsert Repository
        stmt_repo = select(Repository).where(Repository.github_id == repo_payload.id)
        res_repo = await db.execute(stmt_repo)
        repo = res_repo.scalar_one_or_none()

        if not repo:
            repo = Repository(
                github_id=repo_payload.id,
                owner=repo_payload.owner.login,
                name=repo_payload.name,
                full_name=repo_payload.full_name,
                default_branch=repo_payload.default_branch,
                is_active=True,
                webhook_installed=True,
            )
            db.add(repo)
            await db.flush()
        else:
            repo.default_branch = repo_payload.default_branch
            repo.is_active = True
            repo.webhook_installed = True

        # 2. Upsert PullRequest
        stmt_pr = select(PullRequest).where(
            PullRequest.repository_id == repo.id,
            PullRequest.pr_number == pr_payload.number,
        )
        res_pr = await db.execute(stmt_pr)
        pr = res_pr.scalar_one_or_none()

        pr_state = (
            "closed" if action == "closed" else ("merged" if pr_payload.merged_at else "open")
        )

        if not pr:
            pr = PullRequest(
                repository_id=repo.id,
                github_pr_id=pr_payload.id,
                pr_number=pr_payload.number,
                title=pr_payload.title,
                state=pr_state,
                author=pr_payload.user.login,
                base_sha=pr_payload.base.sha,
                head_sha=pr_payload.head.sha,
                base_ref=pr_payload.base.ref,
                head_ref=pr_payload.head.ref,
                merged_at=pr_payload.merged_at,
            )
            db.add(pr)
            await db.flush()
        else:
            pr.title = pr_payload.title
            pr.state = pr_state
            pr.base_sha = pr_payload.base.sha
            pr.head_sha = pr_payload.head.sha
            pr.base_ref = pr_payload.base.ref
            pr.head_ref = pr_payload.head.ref
            pr.merged_at = pr_payload.merged_at

        # 3. Actions: closed
        if action == "closed":
            await db.commit()
            return WebhookProcessingResult(
                status="accepted",
                event="pull_request",
                action=action,
                delivery_id=delivery_id,
                repository=repo.full_name,
                pr_number=pr.pr_number,
                message=f"Pull request #{pr.pr_number} marked as {pr_state}",
            )

        # 4. Actions: opened, reopened, synchronize -> Trigger Analysis
        if action in ("opened", "reopened", "synchronize"):
            # Invalidate older pending/running analyses if this is a synchronize event (new commits pushed)
            if action == "synchronize":
                stmt_invalidate = (
                    update(Analysis)
                    .where(
                        Analysis.pull_request_id == pr.id,
                        Analysis.status.in_(["PENDING", "RUNNING"]),
                    )
                    .values(status="SUPERSEDED", error_message="Superseded by newer commit")
                )
                await db.execute(stmt_invalidate)

            # Create new Analysis record
            analysis = Analysis(
                pull_request_id=pr.id,
                commit_sha=pr.head_sha,
                base_sha=pr.base_sha,
                status="PENDING",
                analysis_version="1.0.0",
            )
            db.add(analysis)
            await db.commit()
            await db.refresh(analysis)

            # Enqueue background task
            job_info = self.queue_manager.enqueue(
                run_pr_analysis_task,
                analysis.id,
                repo.full_name,
                pr.head_sha,
                pr.base_sha,
                job_id=f"analysis_{analysis.id}",
            )

            logger.info(
                f"Analysis {analysis.id} enqueued for {repo.full_name} PR #{pr.pr_number} (Job: {job_info.get('job_id')})"
            )

            return WebhookProcessingResult(
                status="accepted",
                event="pull_request",
                action=action,
                delivery_id=delivery_id,
                repository=repo.full_name,
                pr_number=pr.pr_number,
                commit_sha=pr.head_sha,
                analysis_id=analysis.id,
                message=f"Analysis {analysis.id} successfully initiated",
            )

        await db.commit()
        return WebhookProcessingResult(
            status="accepted",
            event="pull_request",
            action=action,
            delivery_id=delivery_id,
            repository=repo.full_name,
            pr_number=pr.pr_number,
            message=f"PR action {action} processed",
        )

    async def _handle_installation_event(
        self,
        payload: GitHubWebhookPayload,
        delivery_id: str | None,
        db: AsyncSession,
    ) -> WebhookProcessingResult:
        action = payload.action.lower()
        is_active = action in ("created", "added")

        logger.info(f"Processing installation.{action}")

        # Update repository installation status if repositories provided
        if payload.repository:
            stmt_repo = select(Repository).where(Repository.github_id == payload.repository.id)
            res_repo = await db.execute(stmt_repo)
            repo = res_repo.scalar_one_or_none()
            if repo:
                repo.is_active = is_active
                repo.webhook_installed = is_active
                await db.commit()

        return WebhookProcessingResult(
            status="accepted",
            event="installation",
            action=action,
            delivery_id=delivery_id,
            message=f"Installation action {action} recorded",
        )


webhook_handler = WebhookHandlerService()
