"""Application lifecycle, bounded request reading and inference dispatch."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import hmac
import logging
import time

from fastapi import FastAPI, Request
from starlette.requests import ClientDisconnect
from starlette.responses import JSONResponse, Response

from .api import APIError, check_tokens, embedding_response, parse_body
from .cache import EmbeddingCache
from .scheduler import Scheduler

log = logging.getLogger("bge_embedding")


def create_app(config, embedder_factory=None):
    @asynccontextmanager
    async def lifespan(app):
        key = config.auth.api_key
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bge-metal")
        try:
            def load():
                if embedder_factory is not None:
                    return embedder_factory()
                from .inference import Embedder
                return Embedder(config.model.path, config.mlx)
            app.state.embedder = await asyncio.get_running_loop().run_in_executor(executor, load)
            app.state.key = ("Bearer " + key).encode("utf-8")
            app.state.scheduler = Scheduler(app.state.embedder.embed, executor, config.queue)
            app.state.cache = (EmbeddingCache(config.cache.max_bytes)
                               if config.cache.enabled else None)
            log.info("startup ready")
            yield
        finally:
            if hasattr(app.state, "scheduler"):
                await app.state.scheduler.close()
                # Release the model on the same thread that owns inference.
                app.state.scheduler.infer = None
                await asyncio.get_running_loop().run_in_executor(
                    executor, lambda: del_model(app))
            executor.shutdown(wait=True)
            log.info("shutdown complete")

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def health():
        scheduler = getattr(app.state, "scheduler", None)
        ready = scheduler is not None and not scheduler.closing
        return JSONResponse({"status": "ready" if ready else "not_ready"}, 200 if ready else 503)

    @app.post("/v1/embeddings")
    async def embeddings(request: Request):
        started = time.monotonic()
        status, code, size, total = 500, "inference_failed", 0, 0
        job = watcher = None
        hits = dedup = 0
        scheduler = getattr(app.state, "scheduler", None)
        try:
            if scheduler is None or scheduler.closing:
                raise APIError("model_unavailable")
            auth = request.headers.get("authorization", "").encode("utf-8")
            if not hmac.compare_digest(auth, app.state.key):
                raise APIError("invalid_api_key")
            body = bytearray()
            async for chunk in request.stream():
                if len(body) + len(chunk) > config.limits.max_body_bytes:
                    raise APIError("request_too_large")
                body.extend(chunk)
            texts, return_sparse = parse_body(body, config.limits)
            size = len(texts)
            tokens = await asyncio.to_thread(app.state.embedder.tokenize, texts)
            total = check_tokens(tokens, config.limits)
            cache = getattr(app.state, "cache", None)
            cached = ([cache.lookup(item, return_sparse) for item in tokens]
                      if cache is not None else None)
            if cached is not None:
                hits = sum(item is not None for item in cached)
                pending = [item for item, found in zip(tokens, cached) if found is None]
            else:
                pending = tokens
            unique = {}
            for item in pending:
                key = tuple(item)
                if key in unique:
                    dedup += 1
                else:
                    unique[key] = item
            if unique:
                job = scheduler.submit(list(unique.values()), return_sparse)
                watcher = asyncio.create_task(disconnected(request))
                done, _ = await asyncio.wait([job.result, watcher], return_when=asyncio.FIRST_COMPLETED)
                if watcher in done:
                    raise ClientDisconnect()
                computed = job.result.result()
                if cache is not None:
                    cache.store(list(unique.values()), computed, return_sparse)
                by_key = {tuple(ids): embedding
                          for ids, embedding in zip(unique.values(), computed)}
                result = ([found if found is not None else by_key[tuple(item)]
                           for item, found in zip(tokens, cached)]
                          if cached is not None
                          else [by_key[tuple(item)] for item in tokens])
            else:
                result = cached
            response = embedding_response(result, total, return_sparse)
            status, code = 200, "ok"
            return response
        except APIError as error:
            response = error.response()
            status, code = response.status_code, error.code
            return response
        except ClientDisconnect:
            status, code = 499, "client_disconnected"
            return Response(status_code=499)
        except asyncio.CancelledError:
            status, code = 499, "client_disconnected"
            raise
        except Exception:
            error = APIError("inference_failed")
            status, code = 500, error.code
            return error.response()
        finally:
            if watcher:
                watcher.cancel()
            if job:
                scheduler.abandon(job)
            now = time.monotonic()
            if job is not None:
                started_at = job.started_at
                wait_ms = max(0, int(((started_at if started_at is not None else now)
                                      - job.enqueued_at) * 1000))
                exec_ms = (max(0, int(((job.finished_at if job.finished_at is not None else now)
                                       - started_at) * 1000))
                           if started_at is not None else 0)
                ahead = job.ahead
            else:
                wait_ms = exec_ms = ahead = 0
            log.info("path=/v1/embeddings status=%d code=%s seconds=%.3f batch=%d tokens=%d hits=%d wait_ms=%d exec_ms=%d ahead=%d dedup=%d",
                     status, code, now - started, size, total, hits, wait_ms, exec_ms, ahead,
                     dedup if job is not None else 0)
    return app


async def disconnected(request):
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


def del_model(app):
    del app.state.embedder
