import pytest
import asyncio
from contextlib import asynccontextmanager

from framework.asgi_app import App
from framework.depends import Depends
from framework.types import Request


class Connection:
    def __init__(self, ident: int, log: list[str]):
        self.ident = ident
        self.log = log

    def __repr__(self) -> str:
        return f"<Connection({self.ident})>"

    async def begin(self):
        self.log.append(f"Begin:{self.ident}")

    async def commit(self):
        self.log.append(f"Commit:{self.ident}")

    async def rollback(self):
        self.log.append(f"Rollback:{self.ident}")

    @asynccontextmanager
    async def transaction(self):
        await self.begin()
        try:
            yield self
        except Exception:
            await self.rollback()
            raise
        else:
            await self.commit()


class AsyncConnectionPool:
    def __init__(self, size: int, log: list[str]) -> None:
        self.size = size
        self.log = log
        self._opened = False
        self.available: asyncio.Queue = asyncio.Queue()

    async def open(self) -> None:
        if self._opened:
            return

        for i in range(self.size):
            conn = Connection(i, self.log)
            await self.available.put(conn)

        self._opened = True
        self.log.append("pool open")

    async def close(self) -> None:
        self._opened = False
        self.log.append("pool close")

    async def acquire(self) -> Connection:
        conn = await self.available.get()
        self.log.append(f"acquire:{conn.ident}")
        return conn

    async def release(self, conn: Connection) -> None:
        self.log.append(f"release:{conn.ident}")
        await self.available.put(conn)

    @asynccontextmanager
    async def connection(self) -> Connection:
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)


class DummyRequest:
    def __init__(self):
        self.path_params = {}
        self._query = {}
        self._body = None
        self.app = None

    def query_param(self, name: str):
        return self._query.get(name)

    def json(self):
        return self._body


class UserRepo:
    def __init__(self, conn: Connection):
        self.conn = conn

    async def get_user(self, user_id: int) -> dict[str, int]:
        async with self.conn.transaction() as conn:
            self.conn.log.append(f"repo: {user_id}")
            return {"id": user_id}


def make_env():
    app = App()
    req = DummyRequest()
    req.app = app

    log: list[str] = []
    pool = AsyncConnectionPool(2, log=log)
    app.state.pool = pool

    async def get_db(request: Request):
        app_pool = request.app.state.pool
        conn = await app_pool.acquire()
        try:
            yield conn
        finally:
            await app_pool.release(conn)

    async def get_repo(db=Depends(get_db)):
        return UserRepo(db)

    return app, req, log, pool, get_db, get_repo


@asynccontextmanager
async def lifespan(app: App, pool: AsyncConnectionPool):
    await pool.open()
    app.state.pool = pool
    try:
        yield
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_repo_lifecycle():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    @app.get("/h1")
    def handler(repo=Depends(get_repo)):
        repo.conn.log.append("handler")
        return "Ok"

    try:
        await app._call_handler(handler, req)
    finally:
        await pool.close()

    assert log == [
        "pool open",
        "acquire:0",
        "handler",
        "release:0",
        "pool close",
    ]


@pytest.mark.asyncio
async def test_repo_call():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    @app.get("/h2")
    async def handler(repo=Depends(get_repo)):
        await repo.get_user(42)
        repo.conn.log.append("handler")

    try:
        await app._call_handler(handler, req)
    finally:
        await pool.close()

    assert log == [
        "pool open",
        "acquire:0",
        "repo: 42",
        "handler",
        "release:0",
        "pool close",
    ]


@pytest.mark.asyncio
async def test_repo_cleanup_on_exception():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    @app.get("/h3")
    async def handler(repo=Depends(get_repo)):
        repo.conn.log.append("handler")
        raise RuntimeError("Boom")

    with pytest.raises(RuntimeError):
        try:
            await app._call_handler(handler, req)
        finally:
            await pool.close()

    assert log == ["pool open", "acquire:0", "handler", "release:0", "pool close"]


@pytest.mark.asyncio
async def test_pool_open():
    log = []
    pool = AsyncConnectionPool(2, log=log)

    await pool.open()
    assert pool.available.qsize() == 2
    assert log == ["pool open"]


@pytest.mark.asyncio
async def test_pool_acquire_release():
    log = []
    pool = AsyncConnectionPool(2, log=log)

    await pool.open()

    conn = await pool.acquire()
    assert pool.available.qsize() == 1
    assert isinstance(conn, Connection)
    assert conn.ident in {0, 1}

    await pool.release(conn)
    assert pool.available.qsize() == 2


@pytest.mark.asyncio
async def test_pool_reuse_between_requests():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    @app.get("/reuse")
    def handler(repo=Depends(get_repo)):
        repo.conn.log.append(f"handler:{repo.conn.ident}")
        return "Ok"

    try:
        await app._call_handler(handler, req)
        await app._call_handler(handler, req)
    finally:
        await pool.close()

    assert pool.available.qsize() == 2
    assert log == [
        "pool open",
        "acquire:0",
        "handler:0",
        "release:0",
        "acquire:1",
        "handler:1",
        "release:1",
        "pool close",
    ]


@pytest.mark.asyncio
async def test_pool_connection_context_manager():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    try:
        async with pool.connection() as conn:
            log.append(f"work:{conn.ident}")
    finally:
        await pool.close()

    assert log == ["pool open", "acquire:0", "work:0", "release:0", "pool close"]
    assert pool.available.qsize() == 2


@pytest.mark.asyncio
async def test_pool_connection_context_manager_on_exception():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    with pytest.raises(RuntimeError):
        try:
            async with pool.connection() as conn:
                log.append(f"work:{conn.ident}")
                raise RuntimeError("Boom")
        finally:
            await pool.close()

    assert log == ["pool open", "acquire:0", "work:0", "release:0", "pool close"]
    assert pool.available.qsize() == 2


@pytest.mark.asyncio
async def test_pool_lifespan():
    app, req, log, pool, get_db, get_repo = make_env()

    async with lifespan(app, pool):
        async with pool.connection() as conn:
            log.append(f"work:{conn.ident}")

    assert log == ["pool open", "acquire:0", "work:0", "release:0", "pool close"]
    assert pool.available.qsize() == 2


@pytest.mark.asyncio
async def test_transaction_commit():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    try:
        async with pool.connection() as conn:
            async with conn.transaction():
                log.append("work")
    finally:
        await pool.close()

    assert log == [
        "pool open",
        "acquire:0",
        "Begin:0",
        "work",
        "Commit:0",
        "release:0",
        "pool close",
    ]


@pytest.mark.asyncio
async def test_transaction_rollback():
    app, req, log, pool, get_db, get_repo = make_env()
    await pool.open()

    with pytest.raises(RuntimeError):
        try:
            async with pool.connection() as conn:
                async with conn.transaction():
                    log.append("work")
                    raise RuntimeError("Boom")
        finally:
            await pool.close()

    assert log == [
        "pool open",
        "acquire:0",
        "Begin:0",
        "work",
        "Rollback:0",
        "release:0",
        "pool close",
    ]



