from .container import Container
from .routes import Req, Router

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
    from fastapi.responses import JSONResponse, RedirectResponse

    c = container or Container()
    router = Router(c)
    app = FastAPI(title="LivingDocs FE01 - Workspace & Version Control Integration")
    app.state.container = c

    @app.api_route(Router.PREFIX + "/{path:path}", methods=METHODS)
    async def entry(request: Request):
        status, payload, location = await adapt(router, request, run_in_threadpool)
        if location:
            return RedirectResponse(location, status_code=status)
        return JSONResponse(payload, status_code=status)

    return app
