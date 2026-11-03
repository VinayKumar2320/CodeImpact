from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.logging import get_logger
from app.core.security import verify_github_signature
from app.schemas.webhook import WebhookProcessingResult
from app.services.github.webhook_handler import webhook_handler

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/github",
    response_model=WebhookProcessingResult,
    summary="GitHub Webhook Intake Endpoint",
    status_code=status.HTTP_202_ACCEPTED,
)
async def github_webhook_endpoint(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    Ingest and process GitHub pull request, synchronize, and installation events.
    Verifies HMAC-SHA256 signature, deduplicates duplicate deliveries, and enqueues analyses.
    """
    body_bytes = await request.body()

    # 1. HMAC Signature Verification
    if not verify_github_signature(body_bytes, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        logger.warning(f"Webhook signature verification failed for delivery {x_github_delivery}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook signature",
        )

    # 2. Header Validation
    if not x_github_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-GitHub-Event header",
        )

    # 3. Payload Parsing
    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {e}",
        ) from e

    # 4. Delegate to Webhook Handler Service
    result = await webhook_handler.handle_webhook(
        event=x_github_event,
        payload_data=payload,
        delivery_id=x_github_delivery,
        db=db,
    )

    status_code = status.HTTP_202_ACCEPTED
    if result.status == "duplicate":
        status_code = status.HTTP_200_OK

    return JSONResponse(status_code=status_code, content=result.model_dump())
