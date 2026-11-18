from .container import Container
from .router import Req
from .routes import build_router

METHODS = ["GET", "POST", "PUT", "DELETE"]


async def adapt(router, request, runner):
    body = await request.body()
    req = Req(
        request.method,
        request.url.path,
        dict(request.query_params),
        {k.lower(): v for k, v in request.headers.items()},
        body,
    )
    return await runner(router.handle, req)


def create_app(container=None):
    from fastapi import FastAPI, Request
    from fastapi.concurrency import run_in_threadpool
    from fastapi.responses import JSONResponse

    c = container or Container()
    router = build_router(c)
    app = FastAPI(title="LivingDocs FE11 - Dynamic Template Management Library")
    app.state.container = c

    @app.api_route("/api/v1/{path:path}", methods=METHODS)
    async def entry(request: Request):
        status, payload = await adapt(router, request, run_in_threadpool)
        return JSONResponse(payload, status_code=status)

    return app
