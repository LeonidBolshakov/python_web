import pytest

from framework.asgi_app import App
from framework.depends import Depends


class DummyRequest:
    def __init__(
        self,
        *,
        path_params=None,
        query=None,
        body=None,
    ):
        self.path_params = path_params or {}
        self._query = query or {}
        self._body = body

    def query_param(self, name: str):
        return self._query.get(name)

    def json(self):
        return self._body


@pytest.fixture
def app():
    return App()


@pytest.fixture
def dummy_request():
    return DummyRequest()


@pytest.mark.asyncio
async def test_dependency_is_cached_within_one_request(app, dummy_request):
    calls = []

    def get_db():
        calls.append("get_db")
        return object()

    def handler(db1=Depends(get_db), db2=Depends(get_db)):
        return {"same": db1 is db2}

    result = await app._call_handler(handler, dummy_request)

    assert result == {"same": True}
    assert calls == ["get_db"]


@pytest.mark.asyncio
async def test_nested_yield_dependencies_cleanup_in_reverse_order(app, dummy_request):
    events = []

    def dep_a():
        events.append("enter_a")
        yield "A"
        events.append("exit_a")

    def dep_b(a=Depends(dep_a)):
        events.append(f"enter_b:{a}")
        yield "B"
        events.append("exit_b")

    def handler(b=Depends(dep_b)):
        events.append(f"handler:{b}")
        return {"ok": True}

    result = await app._call_handler(handler, dummy_request)

    assert result == {"ok": True}
    assert events == [
        "enter_a",
        "enter_b:A",
        "handler:B",
        "exit_b",
        "exit_a",
    ]


@pytest.mark.asyncio
async def test_cleanup_runs_when_handler_raises(app, dummy_request):
    events = []

    def dep():
        events.append("enter")
        yield "X"
        events.append("exit")

    def handler(x=Depends(dep)):
        events.append(f"handler:{x}")
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await app._call_handler(handler, dummy_request)

    assert events == ["enter", "handler:X", "exit"]


@pytest.mark.asyncio
async def test_sync_yield_dependency_without_yield_raises(app, dummy_request):
    def bad_dep():
        if False:
            yield "never"

    def handler(x=Depends(bad_dep)):
        return x

    with pytest.raises(
        RuntimeError,
        match=r"Yield dependency 'bad_dep' завершилась без yield",
    ):
        await app._call_handler(handler, dummy_request)


@pytest.mark.asyncio
async def test_async_yield_dependency_without_yield_raises(app, dummy_request):
    async def bad_dep():
        if False:
            yield "never"

    def handler(x=Depends(bad_dep)):
        return x

    with pytest.raises(
        RuntimeError,
        match=r"Async yield dependency 'bad_dep' завершилась без yield",
    ):
        await app._call_handler(handler, dummy_request)


@pytest.mark.asyncio
async def test_sync_yield_dependency_with_two_yields_raises_on_cleanup(
    app, dummy_request
):
    events = []

    def bad_dep():
        events.append("enter")
        yield "X"
        events.append("between")
        yield "Y"

    def handler(x=Depends(bad_dep)):
        events.append(f"handler:{x}")
        return {"x": x}

    with pytest.raises(
        RuntimeError,
        match=r"Yield dependency 'bad_dep' должна делать ровно один yield",
    ):
        await app._call_handler(handler, dummy_request)

    assert events == ["enter", "handler:X", "between"]


@pytest.mark.asyncio
async def test_async_yield_dependency_with_two_yields_raises_on_cleanup(
    app, dummy_request
):
    events = []

    async def bad_dep():
        events.append("enter")
        yield "X"
        events.append("between")
        yield "Y"

    def handler(x=Depends(bad_dep)):
        events.append(f"handler:{x}")
        return {"x": x}

    with pytest.raises(
        RuntimeError,
        match=r"Async yield dependency 'bad_dep' должна делать ровно один yield",
    ):
        await app._call_handler(handler, dummy_request)

    assert events == ["enter", "handler:X", "between"]


@pytest.mark.asyncio
async def test_exception_before_first_yield_does_not_register_cleanup(
    app, dummy_request
):
    events = []

    def dep():
        events.append("before")
        raise RuntimeError("fail before yield")
        yield "X"

    def handler(x=Depends(dep)):
        events.append("handler")
        return x

    with pytest.raises(RuntimeError, match="fail before yield"):
        await app._call_handler(handler, dummy_request)

    assert events == ["before"]


@pytest.mark.asyncio
async def test_mixed_sync_and_async_yield_dependencies(app, dummy_request):
    events = []

    def dep1():
        events.append("enter1")
        yield "A"
        events.append("exit1")

    async def dep2(a=Depends(dep1)):
        events.append(f"enter2:{a}")
        yield "B"
        events.append("exit2")

    def handler(b=Depends(dep2)):
        events.append(f"handler:{b}")
        return {"value": b}

    result = await app._call_handler(handler, dummy_request)

    assert result == {"value": "B"}
    assert events == [
        "enter1",
        "enter2:A",
        "handler:B",
        "exit2",
        "exit1",
    ]


@pytest.mark.asyncio
async def test_nested_dependency_is_cached_across_dependency_graph(app, dummy_request):
    calls = []

    def settings():
        calls.append("settings")
        return {"mode": "dev"}

    def repo(cfg=Depends(settings)):
        return cfg

    def service(cfg=Depends(settings), repo_cfg=Depends(repo)):
        return cfg, repo_cfg

    def handler(result=Depends(service)):
        return result

    cfg1, cfg2 = await app._call_handler(handler, dummy_request)

    assert cfg1 == {"mode": "dev"}
    assert cfg2 == {"mode": "dev"}
    assert cfg1 is cfg2
    assert calls == ["settings"]


@pytest.mark.asyncio
async def test_async_normal_dependency_is_supported(app, dummy_request):
    async def get_user():
        return {"id": 1}

    def handler(user=Depends(get_user)):
        return user

    result = await app._call_handler(handler, dummy_request)

    assert result == {"id": 1}


@pytest.mark.asyncio
async def test_sync_dependency_can_depend_on_async_dependency(app, dummy_request):
    async def get_number():
        return 10

    def get_text(n=Depends(get_number)):
        return f"num:{n}"

    def handler(text=Depends(get_text)):
        return text

    result = await app._call_handler(handler, dummy_request)

    assert result == "num:10"


@pytest.mark.asyncio
async def test_async_dependency_can_depend_on_sync_dependency(app, dummy_request):
    def get_number():
        return 10

    async def get_text(n=Depends(get_number)):
        return f"num:{n}"

    def handler(text=Depends(get_text)):
        return text

    result = await app._call_handler(handler, dummy_request)

    assert result == "num:10"


@pytest.mark.asyncio
async def test_cleanup_error_overrides_successful_handler_result(app, dummy_request):
    def dep():
        yield "X"
        raise RuntimeError("cleanup failed")

    def handler(x=Depends(dep)):
        return {"x": x}

    with pytest.raises(RuntimeError, match="cleanup failed"):
        await app._call_handler(handler, dummy_request)


@pytest.mark.asyncio
async def test_cleanup_still_runs_for_nested_dependencies_when_inner_handler_fails(
    app, dummy_request
):
    events = []

    def dep_a():
        events.append("enter_a")
        yield "A"
        events.append("exit_a")

    def dep_b(a=Depends(dep_a)):
        events.append(f"enter_b:{a}")
        yield "B"
        events.append("exit_b")

    def handler(b=Depends(dep_b)):
        events.append(f"handler:{b}")
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        await app._call_handler(handler, dummy_request)

    assert events == [
        "enter_a",
        "enter_b:A",
        "handler:B",
        "exit_b",
        "exit_a",
    ]
