from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.base import RequestResponseEndpoint
from starlette.responses import Response


class DomainError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        self.code, self.message, self.status = code, message, status


def install_errors(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain(request: Request, exc: DomainError) -> JSONResponse:
        return envelope(request, exc.status, exc.code, exc.message)

    @app.exception_handler(HTTPException)
    async def http(request: Request, exc: HTTPException) -> JSONResponse:
        return envelope(request, exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Pydantic errors can include submitted private input: never echo that field.
        details = [
            {"loc": list(e["loc"]), "type": e["type"], "message": e["msg"]} for e in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {"code": "validation_error", "message": "输入不合法", "details": details},
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        import logging

        logging.getLogger("offerpilot.api").error(
            "request_id=%s error_type=%s",
            getattr(request.state, "request_id", "unknown"),
            type(exc).__name__,
        )
        return envelope(
            request, 500, "internal_error", "服务暂时无法完成请求，请凭请求编号检查日志"
        )

    @app.middleware("http")
    async def request_id(request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception as exc:
            # Intercept before ServerErrorMiddleware can print SQL/provider payloads in a traceback.
            import logging

            logging.getLogger("offerpilot.api").error(
                "request_id=%s error_type=%s", request.state.request_id, type(exc).__name__
            )
            from sqlalchemy.exc import IntegrityError

            response = envelope(
                request,
                409 if isinstance(exc, IntegrityError) else 500,
                "integrity_conflict" if isinstance(exc, IntegrityError) else "internal_error",
                "关联关系或唯一约束冲突"
                if isinstance(exc, IntegrityError)
                else "服务暂时无法完成请求，请凭请求编号检查日志",
            )
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        return response


def envelope(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message, "details": []},
            "request_id": getattr(request.state, "request_id", "unknown"),
        },
    )
