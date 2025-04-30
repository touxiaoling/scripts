import tomllib
from pathlib import Path
def load_config():
    toml_file = Path('config.toml')
    with toml_file.open('rb') as f: 
        cfg = tomllib.load(f)
    return cfg
