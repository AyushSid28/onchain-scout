from typing import List
import uuid
from fastapi import APIRouter, Depends, HTTPException
from db.crud import create_api_key, delete_api_key, list_api_keys, update_api_key_name
from schemas import APIKeyDB, APIKeyResponse, CreateApiKeyRequest, UpdateApiKeyRequest
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.session import SessionContainer
from configs.logfire_config import setup_logger

logger = setup_logger(__name__)
api_key_router = APIRouter(prefix="/api_keys", tags=["API Keys"])

@api_key_router.post("/create", response_model=APIKeyResponse)
def create_api__key(
    request: CreateApiKeyRequest,
    session: SessionContainer = Depends(verify_session())
):
    """Create a new API key for a project."""
    db_api_key, raw_key = create_api_key(
        user_id=session.user_id,
        name=request.name,
    )

    # Create response with the raw key (only time it will be shown)
    response = APIKeyResponse(
        id=db_api_key.id,
        user_id=db_api_key.user_id,
        name=db_api_key.name,
        api_key=raw_key,
        created_at=db_api_key.created_at,
        updated_at=db_api_key.updated_at
    )
    logger.info(f"API key created for user {session.user_id}")
    return response

@api_key_router.delete("/", response_model=dict)
def delete__api_key(
    key_id: uuid.UUID,
    session: SessionContainer = Depends(verify_session())
):
    """Delete an API key for a project."""
    success = delete_api_key(key_id=key_id)
    if not success:
        logger.error(f"Failed to delete API key {key_id}")
        raise HTTPException(status_code=404, detail="API key not found")
    logger.info(f"Deleted API key {key_id}")
    return {"message": "API key deleted successfully"}

@api_key_router.get("/", response_model=List[APIKeyDB])
def list_api__keys(
    session: SessionContainer = Depends(verify_session())
):
    """Get all API keys for a user."""
    logger.info(f"Listing API keys for user {session.user_id}")
    return list_api_keys(
        user_id=session.user_id
    )

@api_key_router.patch("/update", response_model=APIKeyDB)
def update__api_key_name(
    request: UpdateApiKeyRequest,
    session: SessionContainer = Depends(verify_session())
):
    """Update the name of an API key."""
    logger.info(f"Updating API key name for key {request.key_id}")
    return update_api_key_name(
        key_id=request.key_id,
        user_id=session.user_id,
        new_name=request.new_name
)