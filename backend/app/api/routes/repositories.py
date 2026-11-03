from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.repository import Repository
from app.schemas.repository import RepositoryCreate, RepositoryResponse

router = APIRouter(prefix="/repositories", tags=["Repositories"])


@router.get("", response_model=list[RepositoryResponse], summary="List registered repositories")
async def list_repositories(
    db: AsyncSession = Depends(get_db),
) -> list[Repository]:
    stmt = select(Repository).order_by(Repository.full_name)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post(
    "",
    response_model=RepositoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a repository",
)
async def create_repository(
    payload: RepositoryCreate,
    db: AsyncSession = Depends(get_db),
) -> Repository:
    stmt = select(Repository).where(Repository.full_name == payload.full_name)
    existing = (await db.execute(stmt)).scalar_one_or_none()
    if existing:
        return existing

    parts = payload.full_name.split("/")
    if len(parts) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository full_name must be in format 'owner/repo'",
        )

    owner, name = parts[0], parts[1]
    repo = Repository(
        id=str(uuid.uuid4()),
        github_id=abs(hash(payload.full_name)) % 100_000_000,
        full_name=payload.full_name,
        owner=owner,
        name=name,
        default_branch=payload.default_branch,
        is_active=True,
    )
    db.add(repo)
    await db.commit()
    await db.refresh(repo)
    return repo


@router.get("/{repository_id}", response_model=RepositoryResponse, summary="Get repository details")
async def get_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> Repository:
    stmt = select(Repository).where(Repository.id == repository_id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.delete(
    "/{repository_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a repository"
)
async def delete_repository(
    repository_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    stmt = select(Repository).where(Repository.id == repository_id)
    repo = (await db.execute(stmt)).scalar_one_or_none()
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    await db.delete(repo)
    await db.commit()
