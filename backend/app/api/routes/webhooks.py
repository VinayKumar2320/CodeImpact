import json

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import verify_github_signature

logger = get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("/github", summary="GitHub Webhook Intake Endpoint")
async def github_webhook_endpoint(
    request: Request,
    x_github_event: str | None = Header(None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(None, alias="X-Hub-Signature-256"),
    x_github_delivery: str | None = Header(None, alias="X-GitHub-Delivery"),
) -> JSONResponse:
    """
    Ingest GitHub pull request and installation events.
    Verifies HMAC-SHA256 signature and event headers.
    """
    body_bytes = await request.body()

    # Signature verification
    if not verify_github_signature(body_bytes, x_hub_signature_256, settings.GITHUB_WEBHOOK_SECRET):
        logger.warning(f"Webhook signature verification failed for delivery {x_github_delivery}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid GitHub webhook signature",
        )

    if not x_github_event:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing X-GitHub-Event header",
        )

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Malformed JSON payload: {e}",
        ) from e

    action = payload.get("action")
    logger.info(
        f"Webhook received: event={x_github_event}, action={action}, delivery={x_github_delivery}"
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "status": "accepted",
            "event": x_github_event,
            "action": action,
            "delivery_id": x_github_delivery,
        },
    )
