import string, random, hashlib
from configs.logfire_config import setup_logger

logger = setup_logger(__name__)

def generate_api_key(length: int = 32) -> str:
    """Generate a random API key of specified length."""
    characters = string.ascii_letters + string.digits
    logger.info(f"Generated API key!")
    return ''.join(random.choice(characters) for _ in range(length))

def generate_coupon_code(length: int = 8) -> str:
    """Generate a random coupon code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def hash_api_key(api_key: str) -> str:
    """Create SHA256 hash of API key"""
    logger.info(f"Hashed API key!")
    return hashlib.sha256(api_key.encode()).hexdigest()