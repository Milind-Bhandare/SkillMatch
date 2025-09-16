from pathlib import Path
import yaml, json

# Base config directory
BASE_DIR = Path(__file__).parent

# Load config.yml
config_path = BASE_DIR / "config.yml"
if not config_path.exists():
    raise RuntimeError(f"config.yml not found at {config_path}")

with open(config_path, "r") as f:
    CONFIG = yaml.safe_load(f)

# Load skills_dict.json
skills_path = BASE_DIR / "skills_dict.json"
if not skills_path.exists():
    raise RuntimeError(f"skills_dict not found at {skills_path}")

with open(skills_path, "r") as f:
    SKILLS_DICT = json.load(f)
