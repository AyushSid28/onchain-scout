from typing import Any, Dict, Optional, Union
from fastapi.responses import JSONResponse
import secrets, uvicorn
from fastapi import Depends, FastAPI, APIRouter, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from supertokens_python.framework.fastapi import get_middleware
from supertokens_python import init, InputAppInfo, SupertokensConfig, get_all_cors_headers
from supertokens_python.recipe import session, userroles, dashboard, thirdparty, emailpassword
from supertokens_python.recipe.session import SessionContainer
from supertokens_python.recipe.emailpassword import InputOverrideConfig as EmailPasswordInputOverrideConfig
from supertokens_python.recipe.emailpassword.interfaces import SignUpOkResult, SignInOkResult, EmailAlreadyExistsError, RecipeInterface as EmailPasswordRecipeInterface
from supertokens_python.recipe.thirdparty.provider import ProviderInput, ProviderConfig, ProviderClientConfig
from supertokens_python.recipe.thirdparty import SignInAndUpFeature
from supertokens_python.recipe.thirdparty import InputOverrideConfig as ThirdPartyInputOverrideConfig
from supertokens_python.recipe.thirdparty.interfaces import SignInUpOkResult, RecipeInterface as ThirdPartyRecipeInterface
from supertokens_python.recipe.thirdparty.types import RawUserInfoFromProvider
from supertokens_python.asyncio import get_users_newest_first
from fastapi.middleware.cors import CORSMiddleware
from db.crud import create_get_user_wallet, create_user
from fastapi.openapi.utils import get_openapi
from fastapi.openapi.docs import get_swagger_ui_html
from routes import *
from configs.config import get_settings
# from configs.logfire_config import setup_telemetry, setup_logger
from configs.logfire_config import init_logging, setup_logger

logger = setup_logger(__name__)
settings = get_settings()
security = HTTPBasic()
app = FastAPI(title="Onchain Scout API", description="API for Onchain Scout", version="1.0.0", docs_url=None, redoc_url=None, openapi_url=None, debug=True)
# Setup telemetry before any routes
init_logging(app)
root_router = APIRouter()

def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    correct_username = secrets.compare_digest(credentials.username, settings.swagger_docs.username)
    correct_password = secrets.compare_digest(credentials.password, settings.swagger_docs.password.get_secret_value())
    if not (correct_username and correct_password):
        logger.error("Incorrect email or password for Swagger docs")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def custom_openapi():
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Add the JWT security scheme to the OpenAPI schema
    openapi_schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
    }

    # Apply the JWT security scheme to all API routes
    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"bearerAuth": []}]
            
    return openapi_schema

def override_thirdpartysigninup(original_implementation: ThirdPartyRecipeInterface) -> ThirdPartyRecipeInterface:
    original_sign_up = original_implementation.sign_in_up

    async def sign_in_up(third_party_id: str, third_party_user_id: str, email: str, is_verified: bool, oauth_tokens: Dict[str, Any], raw_user_info_from_provider: RawUserInfoFromProvider, session: Optional[SessionContainer], should_try_linking_with_session_user: Union[bool, None], tenant_id: str, user_context: Dict[str, Any]):
        # Call the original implementation
        response = await original_sign_up(third_party_id, third_party_user_id, email, is_verified, oauth_tokens, raw_user_info_from_provider, session, should_try_linking_with_session_user, tenant_id, user_context)

        if isinstance(response, SignInUpOkResult):
            # Add custom logic here
            user_id = response.user.id
            create_user_response = create_user(user_id, email)  # Create user in the database
            logger.info(f"User created: {create_user_response}")
            create_wallet_response = create_get_user_wallet(user_id)  # Create wallet for the user
            logger.info(f"Wallet created: {create_wallet_response}")
        else:
            logger.error(f"Failed to create user and wallet in the database: {response}")

        return response

    # Override the sign_in function
    original_implementation.sign_in_up = sign_in_up
    return original_implementation

def override_emailpasswordauth(original_implementation: EmailPasswordRecipeInterface) -> EmailPasswordRecipeInterface:
    original_sign_in = original_implementation.sign_in
    original_sign_up = original_implementation.sign_up

    async def sign_up(email: str, password: str, tenant_id: str, session: Optional[SessionContainer], should_try_linking_with_session_user: Union[bool, None], user_context: Dict[str, Any]):
        # Call the original implementation
        response = await original_sign_up(email, password, tenant_id, session, should_try_linking_with_session_user, user_context)
        if isinstance(response, SignUpOkResult):
            # Add custom logic here
            user_id = response.user.id
            create_user_response = create_user(user_id, email)  # Create user in the database
            create_wallet_response = create_get_user_wallet(user_id)  # Create wallet for the user
        elif isinstance(response, EmailAlreadyExistsError):
            logger.error("Email already exists!")
            users = await get_users_newest_first("")
            users = users.users
            user_id = None
            for i in users:
                if email in i.emails:
                    for j in i.emails:
                        if j == email:
                            user_id = i.id
                            break
            if not user_id:
                logger.error("User not found")
            else:
                create_user_response = create_user(user_id, email)  # Create user in the database
                create_wallet_response = create_get_user_wallet(user_id)  # Create wallet for the user
        else:
            logger.error(f"Failed to create user and wallet in the database: {response}")
        return response

    async def sign_in(email: str, password: str, tenant_id: str, session: Optional[SessionContainer], should_try_linking_with_session_user: Union[bool, None], user_context: Dict[str, Any]):
        # Call the original implementation
        response = await original_sign_in(email, password, tenant_id, session, should_try_linking_with_session_user, user_context)
        if isinstance(response, SignInOkResult):
            # Add custom logic here
            user_id = response.user.id
            create_user_response = create_user(user_id, email)  # Create user in the database
            create_wallet_response = create_get_user_wallet(user_id)  # Create wallet for the user
        else:
            logger.error(f"Failed to create user and wallet in the database: {response}")
        return response

    # Override the sign_up function
    original_implementation.sign_up = sign_up
    original_implementation.sign_in = sign_in
    return original_implementation

providers=[
               ProviderInput(
            config=ProviderConfig(
                third_party_id="google-android",
                clients=[
                    ProviderClientConfig(
                        client_id=settings.google_auth.android.client_id.get_secret_value(),
                        client_secret=""  # Not needed for mobile OAuth,
                    ),
                ],
            ),
        ),
        ProviderInput(
            config=ProviderConfig(
                third_party_id="google-ios",
                clients=[
                    ProviderClientConfig(
                        client_id=settings.google_auth.ios.client_id.get_secret_value(),
                        client_secret=""  # Not needed for mobile OAuth,
                    ),
                ],
            ),
        ),
        ProviderInput(
            config=ProviderConfig(
                third_party_id="google-web",
                clients=[
                    ProviderClientConfig(
                        client_id=settings.google_auth.web.client_id.get_secret_value(),
                        client_secret=""  # Add if needed for web OAuth flow
                    ),
                ],
            ),
        ),
        ProviderInput(
            config=ProviderConfig(
                third_party_id="twitter",
                clients=[
                    ProviderClientConfig(
                        client_id=settings.twitter_auth.client_id.get_secret_value(),
                        client_secret=settings.twitter_auth.client_secret.get_secret_value(),
                        scope=["tweet.read", "users.read"]
                    ),
                ],
            ),
        ),
           ]

logger.info(f"Setting up supertokens")
init(
    app_info=InputAppInfo(
        app_name=settings.supertokens.app_name,
        api_domain=settings.supertokens.api_domain,
        website_domain=settings.supertokens.website_domain,
        api_base_path=settings.supertokens.api_base_path,
        website_base_path=settings.supertokens.website_base_path,
    ),
    supertokens_config=SupertokensConfig(
        # These are the connection details of the app you created on supertokens.com
        connection_uri=settings.supertokens.connection_uri,
        api_key=settings.api_keys.supertokens.get_secret_value(),
    ),
    framework="fastapi",
    recipe_list=[
        emailpassword.init(override=EmailPasswordInputOverrideConfig(functions=override_emailpasswordauth)),
        thirdparty.init(
            sign_in_and_up_feature=SignInAndUpFeature(
                providers=providers
            ),
            override=ThirdPartyInputOverrideConfig(functions=override_thirdpartysigninup)
        ),
        session.init(expose_access_token_to_frontend_in_cookie_based_auth=True),
        userroles.init(),
        dashboard.init()
    ],
    mode="asgi",  # use wsgi if you are running using gunicorn
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        response = JSONResponse(
            content={
            "message": str(e),
            "error_type": e.__class__.__name__,
        },
            status_code=500
        )
    
    # Mandatory CORS headers for all responses
    response.headers["Access-Control-Allow-Origin"] = ",".join(settings.app_config.allowed_origins)
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Expose-Headers"] = ", ".join([
        "st-access-token",
        "st-refresh-token",
        "front-token",
        "anti-csrf"
    ] + get_all_cors_headers())
    
    return response


app.add_middleware(get_middleware())

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app_config.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"] + get_all_cors_headers(),
)

@app.get("/", status_code=200)
def hello_world():
    return "Server is running!"

@app.get("/health")
def health_check():
    return {"status": "UP"}

@app.get("/version")
def get_version():
    return "v1"

@app.get("/docs", include_in_schema=False)
async def get_documentation(username: str = Depends(get_current_username)):
    return get_swagger_ui_html(openapi_url="/openapi.json", title="docs")

@app.get("/openapi.json", include_in_schema=False)
def openapi(username: str = Depends(get_current_username)):
    return custom_openapi()

# onchain-scout-api

## incidents_router
root_router.include_router(incidents_router)

## evaluate_router
root_router.include_router(evaluate_router)

## admin_router
root_router.include_router(admin_router)

## api_keys_router
root_router.include_router(api_key_router)

## payments router
root_router.include_router(payments_router)

app.include_router(root_router)

if __name__ == "__main__":
    uvicorn.run("main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
