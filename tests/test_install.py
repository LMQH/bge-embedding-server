import importlib.util
from pathlib import Path
import plistlib
import stat
import sys

import pytest

from bge_embedding.config import load_config


@pytest.mark.parametrize("legacy", [True, False])
def test_install_creates_private_config_and_migrates_key(config_file, monkeypatch, capsys, legacy):
    root = config_file.parent
    home = root / "home"
    target = home / "Library/LaunchAgents/local.bge-embedding.plist"
    target.parent.mkdir(parents=True)
    if legacy:
        target.write_bytes(plistlib.dumps({"Label": "local.bge-embedding",
                                          "EnvironmentVariables": {"BGE_API_KEY": "legacy-key-sentinel",
                                                                   "BGE_HOST": "127.0.0.2",
                                                                   "BGE_PORT": "8120",
                                                                   "BGE_MODEL_PATH": str(root / "models/bge-m3-mlx-8bit")}}))
    source = Path(__file__).resolve().parents[1]
    (root / "config.example.toml").write_text((source / "config.example.toml").read_text())
    spec = importlib.util.spec_from_file_location("install", source / "deploy/install.py")
    install = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(install)
    monkeypatch.setattr(install, "__file__", str(root / "deploy/install.py"))
    monkeypatch.setattr(Path, "home", staticmethod(lambda: home))
    monkeypatch.setattr(sys, "prefix", str(root / "bge-embedding"))
    private = root / "private/config.toml"
    monkeypatch.setattr(sys, "argv", ["install.py", "--config", str(private)])
    install.main()
    config = load_config(private)
    if legacy:
        assert config.auth.api_key == "legacy-key-sentinel"
        assert config.server.host == "127.0.0.2" and config.server.port == 8120
    else:
        assert len(config.auth.api_key) >= 32
        assert config.server.host == "127.0.0.1" and config.server.port == 8000
    definition = plistlib.loads(target.read_bytes())
    assert definition["ProgramArguments"] == [sys.executable, "-m", "bge_embedding", "--config", str(private)]
    assert "EnvironmentVariables" not in definition
    assert stat.S_IMODE(private.stat().st_mode) == stat.S_IMODE(target.stat().st_mode) == 0o600
    private.write_text(private.read_text().replace(f'port = {config.server.port}', 'port = 8123'))
    before = private.read_bytes()
    install.main()
    assert private.read_bytes() == before
    assert load_config(private).server.port == 8123
    assert config.auth.api_key not in capsys.readouterr().out
