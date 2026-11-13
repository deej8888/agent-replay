from agentreplay_api.database import make_engine
from agentreplay_api.main import create_app
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text


def test_startup_migrations_are_idempotent(tmp_path):
    url = f"sqlite:///{tmp_path / 'trace.db'}"
    for _ in range(2):
        engine = make_engine(url)
        with TestClient(create_app(engine)) as client:
            assert client.post("/v1/demo", json={}).status_code == 201
    engine = make_engine(url)
    assert {"runs", "spans", "alembic_version"} <= set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT COUNT(*) FROM runs")) == 2
    engine.dispose()
