"""FastAPI entry point for the local Trio service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.routes import create_router
from .api.services import RuntimeServices
from .settings import Settings
from .storage.database import Database


def create_app(
    settings: Settings | None = None, services: RuntimeServices | None = None
) -> FastAPI:
    settings = settings or Settings.load()
    runtime = services or RuntimeServices(settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        settings.database_path.parent.mkdir(parents=True, exist_ok=True)
        async with Database.open(settings.database_path) as database:
            await runtime.start(database)
            try:
                yield
            finally:
                await runtime.stop()

    app = FastAPI(title="Trio", lifespan=lifespan)
    app.state.settings = settings
    app.state.services = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_router(runtime))
    return app


def run() -> None:
    import uvicorn

    settings = Settings.load()
    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    run()
