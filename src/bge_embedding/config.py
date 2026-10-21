"""Load one complete private TOML configuration before starting the service."""
from dataclasses import dataclass, fields
import json
import math
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


@dataclass(frozen=True)
class AuthConfig:
    api_key: str


@dataclass(frozen=True)
class ModelConfig:
    path: str


@dataclass(frozen=True)
class QueueConfig:
    max_waiting: int
    wait_timeout_seconds: float


@dataclass(frozen=True)
class LimitsConfig:
    max_body_bytes: int
    max_batch_size: int
    max_tokens_per_text: int
    max_tokens_per_request: int


@dataclass(frozen=True)
class MLXConfig:
    memory_limit_bytes: int
    cache_limit_bytes: int


@dataclass(frozen=True)
class LoggingConfig:
    file: str
    max_bytes: int
    backup_count: int
    level: str


@dataclass(frozen=True)
class Config:
    server: ServerConfig
    auth: AuthConfig
    model: ModelConfig
    queue: QueueConfig
    limits: LimitsConfig
    mlx: MLXConfig
    logging: LoggingConfig


def load_config(path) -> Config:
    path = Path(path).expanduser().resolve()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("Cannot read valid TOML configuration.") from None
    if set(data) != {field.name for field in fields(Config)}:
        raise ValueError("Configuration sections are missing or unknown.")
    sections = {}
    for section in fields(Config):
        values = data[section.name]
        expected = fields(section.type)
        if not isinstance(values, dict) or set(values) != {field.name for field in expected}:
            raise ValueError(f"Invalid fields in {section.name} configuration.")
        for field in expected:
            value = values[field.name]
            valid = type(value) is field.type
            if field.type is float:
                valid = type(value) in (int, float) and math.isfinite(value) and value > 0
            elif field.type is int:
                valid = valid and value > 0
            elif field.type is str:
                valid = valid and bool(value.strip())
            if not valid:
                raise ValueError(f"Invalid configuration value: {section.name}.{field.name}.")
        sections[section.name] = section.type(**values)
    config = Config(**sections)
    if not 1 <= config.server.port <= 65535:
        raise ValueError("Invalid configuration value: server.port.")
    if config.logging.level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("Invalid configuration value: logging.level.")

    def resolve(value):
        return str((path.parent / Path(value).expanduser()).resolve())

    config = Config(**(sections | {
        "model": ModelConfig(resolve(config.model.path)),
        "logging": LoggingConfig(resolve(config.logging.file), config.logging.max_bytes,
                                 config.logging.backup_count, config.logging.level),
    }))
    model_path = Path(config.model.path)
    try:
        metadata = json.loads((model_path / "config.json").read_text())
        tokenizer = json.loads((model_path / "tokenizer_config.json").read_text())
        # XLM-R position IDs start after the padding ID; special tokens count too.
        max_tokens = min(tokenizer["model_max_length"],
                         metadata["max_position_embeddings"] - metadata["pad_token_id"] - 1)
        if not (model_path / "model.safetensors").is_file() or max_tokens < 1:
            raise ValueError
    except (OSError, ValueError, KeyError, TypeError):
        raise ValueError("Local model files and length metadata are required.") from None
    if config.limits.max_tokens_per_text > max_tokens:
        raise ValueError("limits.max_tokens_per_text exceeds the model context length.")
    return config
