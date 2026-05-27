from dotenv import load_dotenv
import warnings

warnings.filterwarnings(action="ignore")
load_dotenv()

from .incidents.crud import incidents_router
from .profiles.evaluate import evaluate_router
from .admin import admin_router
from .payments import payments_router
from .api_keys import api_key_router

__all__ = [
    "incidents_router",
    "evaluate_router",
    "admin_router",
    "payments_router",
    "api_key_router"
    ]