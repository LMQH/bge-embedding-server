"""Write a private launchd definition using this machine's project interpreter."""
import argparse
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import secrets
import sys
import tomllib

from bge_embedding.config import load_config

LABEL = "local.bge-embedding"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    if platform.machine() != "arm64" or Path(sys.prefix).name != "bge-embedding":
        parser.error("Use the native arm64 bge-embedding conda interpreter.")
    root = Path(__file__).resolve().parents[1]
    config_path = Path(args.config).expanduser().resolve()
    target = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        existing = plistlib.loads(target.read_bytes())
        if existing.get("Label") != LABEL:
            parser.error("Refusing to replace a different launchd job.")
        legacy = existing.get("EnvironmentVariables", {})
    else:
        legacy = {}
    if not config_path.exists():
        template = (root / "config.example.toml").read_text()
        defaults = tomllib.loads(template)
        values = {
            "api_key": legacy.get("BGE_API_KEY") or secrets.token_urlsafe(32),
            "path": legacy.get("BGE_MODEL_PATH") or str(
                (root / Path(defaults["model"]["path"]).expanduser()).resolve()),
        }
        if "BGE_HOST" in legacy:
            values["host"] = legacy["BGE_HOST"]
        if "BGE_PORT" in legacy:
            try:
                values["port"] = int(legacy["BGE_PORT"])
            except (ValueError, TypeError):
                parser.error("Invalid legacy port configuration.")
        for name, value in values.items():
            template = re.sub(rf"(?m)^{name} = .*$",
                              lambda match: name + " = " + json.dumps(value), template)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(config_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(template)
    try:
        load_config(config_path)
    except ValueError as error:
        parser.error(str(error))
    config_path.chmod(0o600)
    definition = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, "-m", "bge_embedding", "--config", str(config_path)],
        "WorkingDirectory": str(root),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 10,
        "Umask": 0o077,
        "StandardOutPath": "/dev/null", "StandardErrorPath": "/dev/null",
    }
    # Restrictive mode from creation; do not briefly expose the generated key.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "wb") as stream:
        plistlib.dump(definition, stream)
    print(f"Wrote {target}; configuration: {config_path} (both mode 600). API key is not printed.")


if __name__ == "__main__":
    main()
