from functools import lru_cache
import json
from pathlib import Path
from schemas import Settings

@lru_cache
def get_settings() -> Settings:
    # Look for secrets.json relative to the configs directory (parent directory)
    configs_dir = Path(__file__).parent
    project_root = configs_dir.parent
    config_path = project_root / "secrets.json"

    if not config_path.exists():
        raise FileNotFoundError(f"secrets.json not found at {config_path}")

    with open(config_path) as f:
        config_data = json.load(f)

    return Settings(**config_data)