import asyncio
import logging
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import UUID

import pytest

from tara_agent.agent.models import ToolName
from tara_agent.api.app import create_app
from tara_agent.config import Settings
from tara_agent.data.preprocess import preprocess
from tara_agent.persistence.database import Database


def make_app(tmp_path, **kwargs):
    return create_app(
        Settings(
            environment="test",
            dataset_dir=tmp_path / "missing",
            processed_data_dir=tmp_path / "processed",
            startup_warmup_enabled=True,
            _env_file=None,
            **kwargs,
        )
    )


def test_local_startup_warms_bounded_science_without_model(preprocessable_dataset_dir, tmp_path):
    settings = Settings(
        environment="test",
        dataset_dir=preprocessable_dataset_dir,
        processed_data_dir=tmp_path / "processed",
        startup_warmup_enabled=True,
        _env_file=None,
    )
    preprocess(
        preprocessable_dataset_dir, settings.processed_data_dir, enforce_expected_shape=False
    )
    app = create_app(settings)
    assert app.state.agent is None
    original = app.state.tool_gateway.call
    calls = []

    async def tracked(name, arguments):
        calls.append((name, arguments))
        return await original(name, arguments)

    app.state.tool_gateway.call = tracked

    async def run():
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "completed"

    asyncio.run(run())
    assert (ToolName.FIND_SAMPLES, {"query": {"limit": 2}}) in calls
    diversity = [args["query"] for name, args in calls if name == ToolName.DIVERSITY_ANALYSIS]
    assert {q["marker"] for q in diversity} == {"v4", "v9"}
    assert all(1 <= len(q["sample_ids"]) <= 2 and q["limit"] == 2 for q in diversity)
    assert all(name in {ToolName.FIND_SAMPLES, ToolName.DIVERSITY_ANALYSIS} for name, _ in calls)


def test_pool_auth_and_history_are_read_only_and_capped(tmp_path):
    app = make_app(tmp_path, database_pool_size=2)
    calls = []

    async def ping():
        calls.append("ping")

    async def pool(*, connections):
        calls.append(("pool", connections))

    async def authenticate(token):
        assert token == "tara-startup-readonly-warmup"
        calls.append("authenticate")

    async def history(*, user_id, limit, offset):
        UUID(user_id)
        assert (limit, offset) == (1, 0)
        calls.append("history")
        return [], 0

    async def dispose():
        calls.append("dispose")

    database = SimpleNamespace(ping=ping, warm_up=pool, dispose=dispose)
    app.state.database = database
    app.state.auth_service = SimpleNamespace(authenticate=authenticate)
    app.state.run_repository = SimpleNamespace(list_sessions=history)
    # lifespan 使用工厂中的数据库实例，因此以同一实例构造应用。
    app = create_app(app.state.settings, database=database)
    app.state.auth_service = SimpleNamespace(authenticate=authenticate)
    app.state.run_repository = SimpleNamespace(list_sessions=history)

    async def run():
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "completed"
            assert calls == ["ping", ("pool", 2), "authenticate", "history"]

    asyncio.run(run())
    assert calls[-1] == "dispose"


def test_warmup_failure_does_not_block_startup_or_log_exception_text(tmp_path, caplog):
    app = make_app(tmp_path)

    async def fail(*args):
        raise RuntimeError("sensitive-password-example")

    app.state.tool_gateway = SimpleNamespace(call=fail)

    async def run():
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "failed"

    with caplog.at_level(logging.WARNING):
        asyncio.run(run())
    assert "RuntimeError" in caplog.text
    assert "sensitive-password-example" not in caplog.text


def test_timeout_cancels_optional_warmup_and_still_starts(tmp_path):
    app = make_app(tmp_path, startup_warmup_timeout_seconds=0.01)
    cancelled = []

    async def slow(*args):
        try:
            await asyncio.sleep(30)
        finally:
            cancelled.append(True)

    app.state.tool_gateway = SimpleNamespace(call=slow)

    async def run():
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "failed"

    asyncio.run(run())
    assert cancelled == [True]


def test_startup_waits_for_warmup_and_repeats_after_restart(tmp_path):
    app = make_app(tmp_path)
    calls = []

    async def run():
        started, release, entered = asyncio.Event(), asyncio.Event(), asyncio.Event()

        async def call(*args):
            calls.append(args)
            started.set()
            await release.wait()

        app.state.tool_gateway = SimpleNamespace(call=call)

        async def start():
            async with app.router.lifespan_context(app):
                entered.set()

        task = asyncio.create_task(start())
        await started.wait()
        assert not entered.is_set()
        assert app.state.startup_warmup_status == "running"
        release.set()
        await task
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "completed"

    asyncio.run(run())
    assert len(calls) == 2


def test_disabled_warmup_never_calls_tools(tmp_path):
    app = create_app(
        Settings(
            dataset_dir=tmp_path / "missing",
            processed_data_dir=tmp_path / "processed",
            startup_warmup_enabled=False,
            _env_file=None,
        )
    )

    async def forbidden(*args):
        raise AssertionError("No warmup expected")

    app.state.tool_gateway = SimpleNamespace(call=forbidden)

    async def run():
        async with app.router.lifespan_context(app):
            assert app.state.startup_warmup_status == "disabled"

    asyncio.run(run())


@pytest.mark.parametrize("fail_on", [None, 2])
def test_database_pool_opens_distinct_connections_and_cleans_up(fail_on):
    active, peak, queries = [], [], []

    class Connection:
        async def execute(self, query):
            assert str(query) == "SELECT 1"
            queries.append(True)
            if len(queries) == fail_on:
                raise OSError("test failure")

    class Engine:
        @asynccontextmanager
        async def connect(self):
            connection = Connection()
            active.append(connection)
            peak.append(len(active))
            try:
                yield connection
            finally:
                active.remove(connection)

    database = Database.__new__(Database)
    database._engine = Engine()
    if fail_on:
        with pytest.raises(OSError):
            asyncio.run(database.warm_up(connections=3))
    else:
        asyncio.run(database.warm_up(connections=3))
        assert max(peak) == 3
    assert not active


def test_failed_database_ping_still_disposes_pool(tmp_path):
    disposed = []

    async def ping():
        raise OSError("database unavailable")

    async def dispose():
        disposed.append(True)

    app = create_app(
        make_app(tmp_path).state.settings, database=SimpleNamespace(ping=ping, dispose=dispose)
    )

    async def run():
        async with app.router.lifespan_context(app):
            raise AssertionError("Must not start")

    with pytest.raises(OSError):
        asyncio.run(run())
    assert disposed == [True]
