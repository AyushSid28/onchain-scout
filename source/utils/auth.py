import string, secrets
from fastapi import HTTPException, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from typing import Optional
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.session import SessionContainer
from db.crud import get_api_key_details_from_hash
from source.utils.api_key import hash_api_key

security = HTTPBearer()

def generate_password(length=12):
    characters = string.ascii_letters + string.digits + string.punctuation
    random_password = ''.join(secrets.choice(characters) for _ in range(12))
    return random_password

async def get_user_id(credentials: HTTPAuthorizationCredentials = Security(security),
    session: Optional[SessionContainer] = Depends(verify_session(session_required=False))):
    # First try session authentication
    if session is not None:
        return session.get_user_id()

    api_key = credentials.credentials
    api_key_hash = hash_api_key(api_key)
    api_details = get_api_key_details_from_hash(api_key_hash)
    if api_details is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return str(api_details.user_id)