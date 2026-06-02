from typing import List
from fastapi import APIRouter, HTTPException, Depends
from configs.logfire_config import setup_logger
from db.crud import create_incident, get_incidents
from schemas import IncidentCreate, IncidentResponse
from source.utils.auth import get_user_id

logger = setup_logger(__name__)
incidents_router = APIRouter(prefix="/incidents", tags=["Incidents"])

@incidents_router.post("/create")
async def create_new_incident(incident: IncidentCreate, user_id: str = Depends(get_user_id)):
    """
    Create a new incident

    ### Request Body
     Required fields:
     - x_handle: str
     - username: str
     - project_website: str
     - affiliated_handles: List[str]
     - scam_type: One of ["investment_scam", "impersonation_scam", "giveway_scam", "verification_scam", "pig_butchering", "fake_trdaing_platform", "ai_trading_scam", "affinity_scam", "fake_ico", "fake_presale"]

     Example:
     {
        "x_handle": "0x1234567890abcdef",
        "username": "username",
        "project_website": "https://example.com",
        "affiliated_handles": ["0x1234567890abcdef"],
        "scam_type": "copycat"
     }
    """
    try:
        response = create_incident(incident, user_id)
        if response:
            return {
                "id": response.id,
                "message": "Incident Created Successfully"
            }
        else:
            raise HTTPException(status_code=400, detail="Error creating incident")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@incidents_router.get("/read", response_model=List[IncidentResponse])
async def get_all_incidents(user_id: str = Depends(get_user_id)):
    """
    Get all incidents
    """
    try:
        return get_incidents(user_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))