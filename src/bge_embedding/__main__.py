"""Run exactly one Uvicorn worker with bounded, redacted service logs."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys

import uvicorn

from .app import create_app
from .config import load_config


class SafeServerLog(logging.Filter):
    def filter(self, record):
        # Uvicorn errors may otherwise include exception text or request targets.
        if record.name.startswith("uvicorn"):
            record.msg, record.args = "server lifecycle" if record.levelno < 40 else "server failure", ()
            record.exc_info = record.exc_text = record.stack_info = None
        return True


def configure_logging(config):
    path = Path(config.file)
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(path, maxBytes=config.max_bytes,
                                  backupCount=config.backup_count, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    handler.addFilter(SafeServerLog())
    for name in ("bge_embedding", "uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = [handler]
        logger.propagate = False
        logger.setLevel(config.level)
    logging.getLogger("uvicorn.access").disabled = True


class Server(uvicorn.Server):
    def handle_exit(self, sig, frame):
        scheduler = getattr(self.config.app.state, "scheduler", None)
        if scheduler:
            scheduler.begin_shutdown()
        super().handle_exit(sig, frame)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    try:
        configure_logging(config.logging)
        # Suppress upstream progress output; the application logs safe states.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        from transformers.utils import logging as transformers_logging
        transformers_logging.set_verbosity_error()
        server = Server(uvicorn.Config(create_app(config), host=config.server.host,
                                       port=config.server.port, workers=1, access_log=False, log_config=None))
        server.run()
        return 0 if server.started else 1
    except Exception:
        logging.getLogger("bge_embedding").error("startup failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
