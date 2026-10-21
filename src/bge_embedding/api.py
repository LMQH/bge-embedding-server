"""Strict request validation and safe public errors (SPEC-0001 / SPEC-0002)."""
import json

from starlette.responses import JSONResponse

ERRORS = {
    "invalid_request": (400, "Invalid request.", "invalid_request_error"),
    "input_too_long": (400, "Input exceeds the token limit.", "invalid_request_error"),
    "batch_limit_exceeded": (400, "Batch exceeds the limit.", "invalid_request_error"),
    "invalid_api_key": (401, "Invalid API key.", "authentication_error"),
    "request_too_large": (413, "Request body exceeds the limit.", "invalid_request_error"),
    "queue_full": (429, "Request queue is full.", "rate_limit_error"),
    "queue_timeout": (429, "Request queue wait timed out.", "rate_limit_error"),
    "model_unavailable": (503, "Model is not ready.", "server_error"),
    "inference_failed": (500, "Embedding inference failed.", "server_error"),
}


class APIError(Exception):
    def __init__(self, code, param=None):
        self.code, self.param = code, param
        super().__init__(code)

    def response(self):
        status, message, kind = ERRORS[self.code]
        return JSONResponse({"error": {"message": message, "type": kind,
                                      "param": self.param, "code": self.code}}, status)


def parse_body(body: bytes, limits) -> tuple[list[str], bool]:
    try:
        data = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        raise APIError("invalid_request") from None
    if not isinstance(data, dict) or set(data) - {"model", "input", "encoding_format",
                                                  "return_sparse"}:
        raise APIError("invalid_request")
    if data.get("model") != "bge-m3":
        raise APIError("invalid_request", "model")
    if data.get("encoding_format", "float") != "float":
        raise APIError("invalid_request", "encoding_format")
    return_sparse = data.get("return_sparse", False)
    if type(return_sparse) is not bool:
        raise APIError("invalid_request", "return_sparse")
    texts = data.get("input")
    if isinstance(texts, str):
        texts = [texts]
    if not isinstance(texts, list) or not texts:
        raise APIError("invalid_request", "input")
    if len(texts) > limits.max_batch_size:
        raise APIError("batch_limit_exceeded", "input")
    for i, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise APIError("invalid_request", f"input[{i}]")
        try:
            text.encode("utf-8")
        except UnicodeError:
            raise APIError("invalid_request", f"input[{i}]") from None
    return texts, return_sparse


def check_tokens(token_ids: list[list[int]], limits) -> int:
    for i, ids in enumerate(token_ids):
        if len(ids) > limits.max_tokens_per_text:
            raise APIError("input_too_long", f"input[{i}]")
    total = sum(map(len, token_ids))
    if total > limits.max_tokens_per_request:
        raise APIError("batch_limit_exceeded", "input")
    return total


def embedding_response(embeddings, total, return_sparse=False):
    data = []
    for i, embedding in enumerate(embeddings):
        item = {"object": "embedding", "index": i, "embedding": embedding.dense}
        if return_sparse:
            if embedding.sparse is None:
                raise RuntimeError("Missing sparse output.")
            item["sparse"] = embedding.sparse
        data.append(item)
    return JSONResponse({"object": "list", "model": "bge-m3", "data": data,
                         "usage": {"prompt_tokens": total, "total_tokens": total}})
