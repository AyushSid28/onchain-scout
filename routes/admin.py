from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Depends, Query, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supertokens_python.recipe.emailpassword.syncio import update_email_or_password
from supertokens_python.recipe.emailpassword.asyncio import sign_up, sign_in
from supertokens_python.asyncio import get_user, get_users_newest_first, delete_user
from supertokens_python.recipe.emailpassword.interfaces import UpdateEmailOrPasswordOkResult
from supertokens_python.recipe.session.framework.fastapi import verify_session
from supertokens_python.recipe.session import SessionContainer
from configs.logfire_config import setup_logger
from schemas import PasswordChangeRequest
from source.utils.auth import generate_password, get_user_id
from source.services.sparkpost import send_credentials
from db.crud import create_coupon, create_limit_entry, delete_all_data_for_user, get_all_wallets, update_limit_entry, get_all_limit_entries, update_wallet_balance
from configs.config import get_settings
import nest_asyncio

# Only apply nest_asyncio if not using uvloop (which uvicorn uses by default)
try:
    nest_asyncio.apply()
except ValueError:
    # Skip if uvloop is being used (which is fine - we don't need nest_asyncio with uvloop)
    pass

settings = get_settings()
logger = setup_logger(__name__)
security = HTTPBearer()
admin_router = APIRouter(prefix="/admin", tags=["admin"])

def validate_password(password: str) -> bool:
    """Validate password meets security requirements"""
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.islower() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    if credentials.credentials != settings.api_keys.app_smith.get_secret_value():
        raise HTTPException(status_code=401, detail="Invalid API key")
    return credentials

@admin_router.get("/user-info")
async def get_user_info(user_id: str = Depends(get_user_id)):
    """
    Get user info
    """
    try:
        logger.info("Getting user info")
        user_details = await get_user(user_id)
        return user_details
    except Exception as e:
        logger.error(f"Error getting user info: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@admin_router.post("/change-password")
async def change_password(
    password_data: PasswordChangeRequest,
    session: SessionContainer = Depends(verify_session())
):
    try:
        # Get user details from session
        user_id = session.get_user_id()
        user_details = await get_user(user_id)
        user_email = user_details.emails[0]

        # Validate new password requirements
        if not validate_password(password_data.new_password):
            logger.error("Password does not meet security requirements")
            raise HTTPException(
                status_code=400,
                detail="Password must be at least 8 characters long and contain uppercase, lowercase, and numbers"
            )

        # Verify old password by attempting to sign in
        sign_in_response = await sign_in(
            tenant_id="public",
            email=user_email, 
            password=password_data.old_password
        )

        if not sign_in_response.user:
            logger.error("Current password is incorrect")
            raise HTTPException(
                status_code=401,
                detail="Current password is incorrect"
            )
        # update the users password
        update_response = update_email_or_password(
            session.get_recipe_user_id(),
            email=user_email,
            password=password_data.new_password,
            tenant_id_for_password_policy=session.get_tenant_id(),
        )
        if isinstance(update_response, UpdateEmailOrPasswordOkResult):
            logger.info("Password updated successfully for user email: " + user_email)
        else:
            logger.error("Error updating password")
            raise HTTPException(
                status_code=500,
                detail=update_response.to_json()
            )

        return {
            "status": "success",
            "message": "Password updated successfully"
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"Error changing password: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Error updating password"
        )

@admin_router.post("/create-user")
async def create__user(email: str,
                      credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    if email:
        # Generate a strong random password using letters, digits, and punctuation.
        random_password = generate_password()
        # Create the user using SuperTokens' emailpassword sign up function.
        signup_response = await sign_up("",email, random_password)
        if signup_response.status == "EMAIL_ALREADY_EXISTS_ERROR":
            return {"status": "success", "message": "User added to staging"}
        if signup_response.status != "OK":
            raise HTTPException(
                status_code=400,
                detail=f"User creation failed - {signup_response.status}"
            )
        user_id = signup_response.user.id
        try:
            mail_send_resp = send_credentials(email, random_password)
            logger.info(f"Email sent to {email} - {mail_send_resp}")
        except Exception as e:
            logger.error(f"Email sending failed: {str(e)}")
            raise e
        limit_entry = create_limit_entry(user_id, email)
        return {"status": "success", "message": "User created and credentials sent"}
    else:
        raise HTTPException(
            status_code=400,
            detail="Email is required"
        )

@admin_router.patch("/update-limit/{email}")
async def update_limit(email: str,
                       eval_limit: int = Query(..., gt=0),
                       credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    try:
        limit_entry = update_limit_entry(email, eval_limit)
        if not limit_entry:
            raise HTTPException(
                status_code=400,
                detail="An error occurred, cannot update limit entry"
            )
        return limit_entry
    except HTTPException as e:
        logger.error(f"Error updating user limit: {str(e)}")
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail
        )
    except Exception as e:
        logger.error(f"Error updating user limit: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An error occurred, cannot update limit entry"
        )

@admin_router.get("/list-user-wallets")
async def list_wallets(credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    wallets = get_all_wallets()
    return wallets

@admin_router.patch("/update-wallet-balance/{email}/{amount}")
async def update_wallet__balance(email: str, amount: float, credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    wallet = update_wallet_balance(email, amount)
    return wallet

@admin_router.get("/list-users")
async def list_users(credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    limit_entries = get_all_limit_entries()
    return limit_entries

@admin_router.get("/list-st-users")
async def list_st_users(session: SessionContainer = Depends(verify_session())):
    users = await get_users_newest_first("")
    return users

@admin_router.delete("/delete-st-user/{user_id}")
async def delete_st_user(user_id: str, session: SessionContainer = Depends(verify_session())):
    res = await delete_user(user_id)
    return {"status": "success"}

@admin_router.delete("/delete-user/{email}")
async def delete_user_data(email: str, credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    users = await get_users_newest_first("")
    users = users.users
    user_id = None
    for i in users:
        if email in i.emails:
            for j in i.emails:
                if j == email:
                    user_id = i.id
                    logger.info(f"User ID: {user_id}")
                    break
    if not user_id:
        raise HTTPException(status_code=404, detail="User not found")
    res_st = await delete_user(user_id)
    res = delete_all_data_for_user(user_id)
    if not res:
        raise HTTPException(status_code=500, detail="Failed to delete user data")
    return {"status": "success"}

@admin_router.post("/create-coupon", response_model=Dict[str, Any])
async def create_coupon_code(amount: float, email: str, credentials: HTTPAuthorizationCredentials = Depends(verify_api_key)):
    """Create a coupon code and send it via email (admin only)"""
    coupon_data = create_coupon(amount, email)
    if not coupon_data:
        raise HTTPException(status_code=500, detail="Failed to create coupon")
    return coupon_data