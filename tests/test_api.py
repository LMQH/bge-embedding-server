import asyncio
import json
import logging
import threading
from dataclasses import replace
from pathlib import Path
from contextlib import asynccontextmanager

import httpx
import pytest

from bge_embedding.app import create_app
from bge_embedding.config import load_config
from bge_embedding.inference import Embedding

KEY = "test-key-sentinel-950d"
TEXT = "user-text-sentinel-781b"
AUTH = {"Authorization": f"Bearer {KEY}"}


class FakeEmbedder:
    def __init__(self):
        self.calls = []
        self.fail = False
        self.gate = threading.Event()
        self.gate.set()
        self.started = threading.Event()

    def tokenize(self, texts):
        return [[ord(t[0])] * (len(t) + 2) for t in texts]

    def embed(self, tokens, return_sparse=False):
        self.calls.append(tokens)
        self.started.set()
        assert self.gate.wait(10), "Test did not release inference"
        if self.fail:
            raise RuntimeError(TEXT + KEY)
        result = []
        for ids in tokens:
            sparse = {str(ids[0]): 0.5, str(ids[1]): 0.25} if return_sparse else None
            result.append(Embedding([1.0] + [0.0] * 1023, sparse))
        return result


class TokenEmbedder(FakeEmbedder):
    def embed(self, tokens, return_sparse=False):
        self.calls.append(tokens)
        self.started.set()
        return [Embedding([float(ids[0])] + [0.0] * 1023, None) for ids in tokens]


@asynccontextmanager
async def client_for(settings, model=None):
    model = model or FakeEmbedder()
    app = create_app(settings, lambda: model)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            yield client, model, app


def payload(text="你好", **extra):
    return {"model": "bge-m3", "input": text, **extra}


@pytest.mark.smoke
async def test_success_preserves_text_usage_and_order(settings):
    async with client_for(settings) as (client, model, _):
        texts = ["  中文  ", "English"]
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(texts))
        assert r.status_code == 200
        body = r.json()
        assert body["model"] == "bge-m3" and body["object"] == "list"
        assert [x["index"] for x in body["data"]] == [0, 1]
        assert all(len(x["embedding"]) == 1024 for x in body["data"])
        assert body["usage"] == {"prompt_tokens": sum(map(len, texts)) + 4,
                                  "total_tokens": sum(map(len, texts)) + 4}
        assert model.calls[0][0][0] == ord(" ")
        assert (await client.get("/healthz")).json() == {"status": "ready"}


@pytest.mark.smoke
async def test_sparse_is_opt_in_and_preserves_order(settings):
    async with client_for(settings) as (client, model, _):
        texts = ["中文", "English"]
        r = await client.post("/v1/embeddings", headers=AUTH,
                              json=payload(texts, return_sparse=True))
        assert r.status_code == 200
        data = r.json()["data"]
        assert [item["index"] for item in data] == [0, 1]
        assert all(item["sparse"] for item in data)
        assert all(key.isdigit() and value > 0
                   for item in data for key, value in item["sparse"].items())
        assert data[0]["sparse"] != data[1]["sparse"]
        assert all(len(item["embedding"]) == 1024 for item in data)

        for extra in ({}, {"return_sparse": False}):
            r = await client.post("/v1/embeddings", headers=AUTH, json=payload(texts, **extra))
            assert r.status_code == 200
            assert all("sparse" not in item for item in r.json()["data"])


@pytest.mark.parametrize("value", [None, "", " \n\t", [], 12, True, [1], [["x"]], ["ok", None], ["ok", " "]])
async def test_invalid_input_never_infers(value, settings):
    async with client_for(settings) as (client, model, _):
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(value))
        assert r.status_code == 400 and r.json()["error"]["code"] == "invalid_request"
        assert model.calls == []


@pytest.mark.parametrize("change", [{"model": None}, {"model": "other"}, {"model": ["bge-m3"]},
                                    {"encoding_format": "base64"}, {"encoding_format": None},
                                    {"return_sparse": "true"}, {"return_sparse": 1},
                                    {"return_sparse": None}, {"return_sparse": []},
                                    {"return_sparse": {}},
                                    {"user": "x"}, {"dimensions": 1024}])
async def test_strict_fields(change, settings):
    async with client_for(settings) as (client, model, _):
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload() | change)
        assert r.status_code == 400 and not model.calls


@pytest.mark.parametrize("body", [b"{", b"[]", b"null", b'{}', b'{"model":"bge-m3"}', b'"text"', b'\xff', b'{"model":"bge-m3","input":"\\ud800"}'])
async def test_malformed_body(body, settings):
    async with client_for(settings) as (client, model, _):
        r = await client.post("/v1/embeddings", headers=AUTH, content=body)
        assert r.status_code == 400 and not model.calls


async def test_limits_inclusive_and_entire_batch_validation(settings):
    async with client_for(settings) as (client, model, _):
        for text, status, code in [("a" * 8190, 200, None), ("a" * 8191, 400, "input_too_long"),
                                   (["a"] * 16, 200, None), (["a"] * 17, 400, "batch_limit_exceeded"),
                                   (["a" * 8190] * 4, 200, None),
                                   (["a" * 8190] * 4 + ["a"], 400, "batch_limit_exceeded")]:
            before = len(model.calls)
            r = await client.post("/v1/embeddings", headers=AUTH, json=payload(text))
            assert r.status_code == status
            if code:
                assert r.json()["error"]["code"] == code and len(model.calls) == before
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(["ok", "a" * 8191]))
        assert r.json()["error"]["param"] == "input[1]"
        small = json.dumps(payload("a")).encode()
        r = await client.post("/v1/embeddings", headers=AUTH, content=small + b" " * (settings.limits.max_body_bytes - len(small)))
        assert r.status_code == 200
        async def chunks():
            yield small
            yield b" " * settings.limits.max_body_bytes
        r = await client.post("/v1/embeddings", headers=AUTH, content=chunks())
        assert r.status_code == 413 and r.json()["error"]["code"] == "request_too_large"


async def test_errors_and_logs_do_not_echo_secrets(caplog, settings):
    caplog.set_level(logging.INFO, logger="bge_embedding")
    async with client_for(settings) as (client, model, _):
        for headers in ({}, {"Authorization": "Bearer wrong-" + KEY}):
            r = await client.post("/v1/embeddings", headers=headers, json=payload(TEXT))
            assert r.status_code == 401
            assert KEY not in r.text and TEXT not in r.text
        assert (await client.post("/v1/embeddings", headers=AUTH, json=payload(TEXT))).status_code == 200
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload([TEXT, None]))
        assert r.status_code == 400
        model.fail = True
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(TEXT + "-fail"))
        assert r.status_code == 500
        assert r.json()["error"] == {"message": "Embedding inference failed.", "type": "server_error",
                                     "param": None, "code": "inference_failed"}
    assert KEY not in caplog.text and TEXT not in caplog.text
    assert "[1.0, 0.0" not in caplog.text


async def until(predicate):
    async with asyncio.timeout(5):
        while not predicate():
            await asyncio.sleep(0.005)


async def test_http_fifo_overload_health_and_shutdown(settings):
    model = FakeEmbedder()
    model.gate.clear()
    async with client_for(settings, model) as (client, _, app):
        async def post(text):
            return await client.post("/v1/embeddings", headers=AUTH, json=payload(text))
        active = asyncio.create_task(post("a"))
        await until(model.started.is_set)
        waiting = []
        for i, text in enumerate("bcdefghijklmnopqrst"):
            waiting.append(asyncio.create_task(post(text)))
            await until(lambda: len(app.state.scheduler.waiting) == i + 1)
        assert len(model.calls) == 1
        rejected = await post("u")
        assert rejected.status_code == 429
        assert rejected.json()["error"]["code"] == "queue_full"
        assert rejected.headers["retry-after"] == "1"
        assert (await client.get("/healthz")).status_code == 200
        model.gate.set()
        assert all(r.status_code == 200 for r in await asyncio.gather(active, *waiting))
        assert [x[0][0] for x in model.calls] == list(map(ord, "abcdefghijklmnopqrst"))
        app.state.scheduler.begin_shutdown()
        assert (await post("z")).status_code == 503
        assert (await client.get("/healthz")).status_code == 503


async def test_client_disconnect_releases_queue_but_not_active_slot(settings):
    model = FakeEmbedder()
    model.gate.clear()
    async with client_for(settings, model) as (client, _, app):
        active = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("a")))
        await until(model.started.is_set)
        active.cancel()
        with pytest.raises(asyncio.CancelledError):
            await active
        queued = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("b")))
        await until(lambda: len(app.state.scheduler.waiting) == 1)
        queued.cancel()
        with pytest.raises(asyncio.CancelledError):
            await queued
        assert len(app.state.scheduler.waiting) == 0
        next_job = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("c")))
        await until(lambda: len(app.state.scheduler.waiting) == 1)
        assert len(model.calls) == 1
        model.gate.set()
        assert (await next_job).status_code == 200
        assert [x[0][0] for x in model.calls] == list(map(ord, "ac"))


async def test_queue_timeout_and_shutdown_waiters(caplog, settings):
    caplog.set_level(logging.INFO, logger="bge_embedding")
    model = FakeEmbedder()
    model.gate.clear()
    async with client_for(settings, model) as (client, _, app):
        active = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("a")))
        await until(model.started.is_set)
        assert app.state.scheduler.wait_seconds == 30.0
        app.state.scheduler.wait_seconds = 0.03
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload("b"))
        assert r.status_code == 429 and r.json()["error"]["code"] == "queue_timeout"
        assert r.headers["retry-after"] == "1"
        line = [record.getMessage() for record in caplog.records
                if "code=queue_timeout" in record.getMessage()][-1]
        assert "exec_ms=0" in line
        assert not app.state.scheduler.waiting
        app.state.scheduler.wait_seconds = 30
        queued = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("c")))
        await until(lambda: len(app.state.scheduler.waiting) == 1)
        app.state.scheduler.begin_shutdown()
        assert (await queued).status_code == 503
        assert len(model.calls) == 1 and not active.done()
        model.gate.set()
        assert (await active).status_code == 200


@pytest.mark.smoke
async def test_missing_key_fails_startup(config_file):
    config_file.write_text(config_file.read_text().replace(KEY, "  "))
    with pytest.raises(ValueError, match="auth.api_key"):
        load_config(config_file)


async def test_asgi_disconnect_event_frees_waiting_slot(settings):
    model = FakeEmbedder()
    model.gate.clear()
    async with client_for(settings, model) as (client, _, app):
        active = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("a")))
        await until(model.started.is_set)
        events = asyncio.Queue()
        await events.put({"type": "http.request", "body": json.dumps(payload("b")).encode(), "more_body": False})
        sent = []
        async def send(event):
            sent.append(event)
        scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST",
                 "scheme": "http", "path": "/v1/embeddings", "raw_path": b"/v1/embeddings",
                 "query_string": b"", "headers": [(b"authorization", AUTH["Authorization"].encode())],
                 "client": ("127.0.0.1", 1234), "server": ("test", 80)}
        request = asyncio.create_task(app(scope, events.get, send))
        await until(lambda: len(app.state.scheduler.waiting) == 1)
        await events.put({"type": "http.disconnect"})
        await request
        assert not app.state.scheduler.waiting and len(model.calls) == 1
        model.gate.set()
        assert (await active).status_code == 200


async def test_startup_failure_is_not_ready(settings):
    def broken_load():
        raise RuntimeError("load failed")
    app = create_app(settings, broken_load)
    with pytest.raises(RuntimeError):
        async with app.router.lifespan_context(app):
            pytest.fail("Failed model marked ready")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/healthz")).status_code == 503


def test_rotating_logs_redact_server_errors(settings):
    from bge_embedding.__main__ import configure_logging
    names = ("bge_embedding", "uvicorn", "uvicorn.error")
    originals = {name: (logging.getLogger(name).handlers[:], logging.getLogger(name).propagate,
                        logging.getLogger(name).level)
                 for name in names}
    try:
        configured = replace(settings.logging, max_bytes=12345, backup_count=3, level="WARNING")
        configure_logging(configured)
        logger = logging.getLogger("uvicorn.error")
        try:
            raise RuntimeError(TEXT + KEY)
        except RuntimeError:
            logger.exception("failed %s", TEXT)
        handler = logger.handlers[0]
        assert handler.maxBytes == 12345 and handler.backupCount == 3
        assert logger.level == logging.WARNING
        handler.flush()
        content = Path(settings.logging.file).read_text()
        assert "server failure" in content and TEXT not in content and KEY not in content
        handler.close()
    finally:
        for name, (handlers, propagate, level) in originals.items():
            logging.getLogger(name).handlers = handlers
            logging.getLogger(name).propagate = propagate
            logging.getLogger(name).setLevel(level)


async def test_custom_request_limits_and_queue_settings(settings):
    limits = replace(settings.limits, max_body_bytes=100, max_batch_size=2,
                     max_tokens_per_text=5, max_tokens_per_request=7)
    config = replace(settings, limits=limits,
                     queue=replace(settings.queue, max_waiting=1, wait_timeout_seconds=0.05))
    async with client_for(config) as (client, model, app):
        async def post(text):
            return await client.post("/v1/embeddings", headers=AUTH, json=payload(text))
        assert (await post("abc")).status_code == 200
        assert (await post("abcd")).json()["error"]["code"] == "input_too_long"
        assert (await post(["a", "b", "c"])).json()["error"]["code"] == "batch_limit_exceeded"
        assert (await post(["ab", "cd"])).json()["error"]["code"] == "batch_limit_exceeded"
        assert (await post("x" * 101)).status_code == 413
        model.started.clear()
        model.gate.clear()
        active = asyncio.create_task(post("a"))
        try:
            await until(model.started.is_set)
            waiting = asyncio.create_task(post("b"))
            await until(lambda: len(app.state.scheduler.waiting) == 1)
            assert (await post("c")).json()["error"]["code"] == "queue_full"
            assert (await waiting).json()["error"]["code"] == "queue_timeout"
        finally:
            model.gate.set()
            assert (await active).status_code == 200


@pytest.mark.smoke
async def test_cache_hit_is_bit_identical_and_skips_inference(settings):
    async with client_for(settings) as (client, model, _):
        first = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        assert first.status_code == 200
        inferred = len(model.calls)
        second = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        assert second.status_code == 200
        assert second.json() == first.json()
        assert len(model.calls) == inferred


async def test_partial_hit_infers_only_missing(settings):
    class TokenEmbedder(FakeEmbedder):
        def embed(self, tokens, return_sparse=False):
            self.calls.append(tokens)
            self.started.set()
            assert self.gate.wait(10), "Test did not release inference"
            return [Embedding([float(ids[0])] + [0.0] * 1023, None) for ids in tokens]

    model = TokenEmbedder()
    async with client_for(settings, model) as (client, _model, _):
        first = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        assert first.status_code == 200
        cached_lead = first.json()["data"][0]["embedding"][0]
        before = len(model.calls)
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(["你好", "English"]))
        assert r.status_code == 200
        data = r.json()["data"]
        assert [item["index"] for item in data] == [0, 1]
        assert data[0]["embedding"][0] == cached_lead
        assert data[1]["embedding"][0] == float(ord("E"))
        assert r.json()["usage"] == {"prompt_tokens": 13, "total_tokens": 13}
        assert len(model.calls) == before + 1
        assert model.calls[-1] == [[ord("E")] * 9]


async def test_full_hit_bypasses_busy_scheduler(settings):
    async with client_for(settings) as (client, model, _):
        await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        model.gate.clear()
        try:
            r = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        finally:
            model.gate.set()
        assert r.status_code == 200
        assert r.json()["data"][0]["embedding"] == [1.0] + [0.0] * 1023
        assert len(model.calls) == 1


async def test_sparse_cache_respects_flag_and_roundtrip(settings):
    async with client_for(settings) as (client, model, _):
        sparse = await client.post("/v1/embeddings", headers=AUTH,
                                   json=payload("你好", return_sparse=True))
        dense = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        warm = await client.post("/v1/embeddings", headers=AUTH,
                                 json=payload("你好", return_sparse=True))
        assert sparse.json() == warm.json()
        assert "sparse" not in dense.json()["data"][0]
        assert len(model.calls) == 2


async def test_cache_disabled_by_configuration(settings):
    disabled = replace(settings, cache=replace(settings.cache, enabled=False))
    async with client_for(disabled) as (client, model, _):
        first = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        second = await client.post("/v1/embeddings", headers=AUTH, json=payload("你好"))
        assert first.json() == second.json()
        assert len(model.calls) == 2


async def test_inference_failure_does_not_backfill(settings):
    async with client_for(settings) as (client, model, _):
        text = "失败不回填文本"
        model.fail = True
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(text))
        assert r.status_code == 500
        model.fail = False
        before = len(model.calls)
        assert (await client.post("/v1/embeddings", headers=AUTH, json=payload(text))).status_code == 200
        assert len(model.calls) == before + 1


async def test_client_disconnect_does_not_backfill(settings):
    async with client_for(settings) as (client, model, _):
        text = "断开不回填文本"
        model.gate.clear()
        task = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload(text)))
        await until(model.started.is_set)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        model.gate.set()
        await asyncio.sleep(0.05)
        before = len(model.calls)
        assert (await client.post("/v1/embeddings", headers=AUTH, json=payload(text))).status_code == 200
        assert len(model.calls) == before + 1


@pytest.mark.parametrize("cache_enabled", [True, False])
async def test_duplicate_texts_are_inferred_once(cache_enabled, caplog, settings):
    caplog.set_level(logging.INFO, logger="bge_embedding")
    if not cache_enabled:
        settings = replace(settings, cache=replace(settings.cache, enabled=False))
    model = TokenEmbedder()
    async with client_for(settings, model) as (client, _, _):
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(["a", "b", "a"]))
        assert r.status_code == 200
        data = r.json()["data"]
        assert [item["index"] for item in data] == [0, 1, 2]
        assert [item["embedding"][0] for item in data] == [97.0, 98.0, 97.0]
        assert len(model.calls) == 1
        assert model.calls[0] == [[97, 97, 97], [98, 98, 98]]
        assert r.json()["usage"] == {"prompt_tokens": 9, "total_tokens": 9}
    line = [record.getMessage() for record in caplog.records
            if record.getMessage().startswith("path=/v1/embeddings")][-1]
    assert "batch=3" in line and "dedup=1" in line


async def test_request_log_includes_queue_and_exec_metrics(caplog, settings):
    caplog.set_level(logging.INFO, logger="bge_embedding")
    model = FakeEmbedder()
    model.gate.clear()
    async with client_for(settings, model) as (client, _, app):
        active = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("a")))
        await until(model.started.is_set)
        queued = asyncio.create_task(client.post("/v1/embeddings", headers=AUTH, json=payload("b")))
        await until(lambda: len(app.state.scheduler.waiting) == 1)
        model.gate.set()
        assert (await active).status_code == 200
        assert (await queued).status_code == 200

    lines = [record.getMessage() for record in caplog.records
             if record.getMessage().startswith("path=/v1/embeddings")]
    assert len(lines) == 2
    metrics = {}
    for line in lines:
        fields = dict(part.split("=", 1) for part in line.split() if "=" in part)
        assert {"wait_ms", "exec_ms", "ahead", "dedup"} <= fields.keys()
        assert all(fields[name].isdigit() for name in ("wait_ms", "exec_ms", "ahead", "dedup"))
        metrics[int(fields["ahead"])] = fields
    assert set(metrics) == {0, 1}
    assert int(metrics[1]["wait_ms"]) >= 0
    assert int(metrics[1]["exec_ms"]) >= 0


async def test_retry_after_only_on_overload(settings):
    async with client_for(settings) as (client, model, _):
        r = await client.post("/v1/embeddings", headers=AUTH, json=payload(""))
        assert r.status_code == 400 and "retry-after" not in r.headers
        r = await client.post("/v1/embeddings", headers={"Authorization": "Bearer wrong"},
                              json=payload("a"))
        assert r.status_code == 401 and "retry-after" not in r.headers
