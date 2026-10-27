"""Bound requests before multipart parsing, including chunked requests.

Spools at most the configured request budget to a temporary file; always closes
it. A reverse proxy must additionally impose connection/time/concurrency limits.
"""
from tempfile import SpooledTemporaryFile
from starlette.responses import JSONResponse
from utils import limits


class BodyLimitMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = dict(scope.get("headers", []))
        try:
            declared = int(headers.get(b"content-length", b"0"))
            if declared < 0:
                raise ValueError
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length."}, 400)(scope, receive, send)
        if declared > limits.REQUEST_BYTES:
            return await JSONResponse({"detail": "Request exceeds the configured size limit."}, 413)(scope, receive, send)
        with SpooledTemporaryFile(max_size=65536) as body:
            size = 0
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                chunk = message.get("body", b"")
                size += len(chunk)
                if size > limits.REQUEST_BYTES:
                    return await JSONResponse({"detail": "Request exceeds the configured size limit."}, 413)(scope, receive, send)
                body.write(chunk)
                if not message.get("more_body", False):
                    break
            body.seek(0)
            async def replay():
                chunk = body.read(65536)
                return {"type": "http.request", "body": chunk, "more_body": body.tell() < size}
            await self.app(scope, replay, send)
