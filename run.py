"""Entry point. Spawns PROCESS A (substrate) from inside the server lifespan.
reload MUST be False — uvicorn's reloader does not mix with multiprocessing spawn."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("server.app:app", host="127.0.0.1", port=8000, reload=False, log_level="info")
