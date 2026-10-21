"""Minimal real HTTP smoke using the service's private TOML configuration."""
import argparse
from pathlib import Path
import plistlib
import time

import httpx
import numpy as np

from bge_embedding.config import load_config


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--sparse", action="store_true",
                        help="Also request and check sparse output.")
    parser.add_argument("--long", action="store_true",
                        help="Also send an 8192-token input.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config")
    source.add_argument("--launchd", action="store_true")
    args = parser.parse_args()
    if args.launchd:
        definition = plistlib.loads((Path.home() / "Library/LaunchAgents/local.bge-embedding.plist").read_bytes())
        arguments = definition["ProgramArguments"]
        args.config = arguments[arguments.index("--config") + 1]
    config = load_config(args.config)
    host = config.server.host
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1" if host == "0.0.0.0" else "::1"
    if ":" in host:
        host = f"[{host}]"
    url = args.url or f"http://{host}:{config.server.port}"
    headers = {"Authorization": "Bearer " + config.auth.api_key}

    def check_item(item):
        vector = np.asarray(item["embedding"])
        assert vector.shape == (1024,) and np.isfinite(vector).all()
        assert abs(np.linalg.norm(vector) - 1) <= 1e-5
        if args.sparse:
            assert item["sparse"]
            assert all(key.isdigit() and np.isfinite(value) and value > 0
                       for key, value in item["sparse"].items())
        else:
            assert "sparse" not in item

    with httpx.Client(base_url=url, timeout=120, trust_env=False) as client:
        assert client.get("/healthz").json() == {"status": "ready"}
        request = {"model": "bge-m3", "input": "知识库查询", "encoding_format": "float"}
        if args.sparse:
            request["return_sparse"] = True
        assert client.post("/v1/embeddings", json=request).status_code == 401
        for texts in ("知识库查询", ["知识库文档", "An English query"]):
            response = client.post("/v1/embeddings", headers=headers, json=request | {"input": texts})
            assert response.status_code == 200
            data = response.json()
            expected_size = 1 if isinstance(texts, str) else len(texts)
            assert len(data["data"]) == expected_size
            assert [item["index"] for item in data["data"]] == list(range(expected_size))
            assert data["usage"]["prompt_tokens"] == data["usage"]["total_tokens"] > 0
            for item in data["data"]:
                check_item(item)
        if args.long:
            started = time.monotonic()
            response = client.post("/v1/embeddings", headers=headers,
                                   json=request | {"input": "test " * 8190})
            elapsed = time.monotonic() - started
            assert response.status_code == 200
            data = response.json()
            assert data["usage"]["prompt_tokens"] == 8192
            assert len(data["data"]) == 1
            check_item(data["data"][0])
            print(f"PASS: 8192 tokens, {elapsed:.2f}s")
    print("PASS: health, authentication, single input, two-item batch, 1024 finite normalized values"
          + (", sparse" if args.sparse else "") + (", 8192 tokens" if args.long else ""))


if __name__ == "__main__":
    main()
