import os

import pytest
from agentreplay_api.database import make_engine
from agentreplay_api.main import create_app
from fastapi.testclient import TestClient


@pytest.mark.skipif(
    not os.getenv("AGENTREPLAY_TEST_POSTGRES"),
    reason="Set AGENTREPLAY_TEST_POSTGRES to test PostgreSQL",
)
def test_postgres_migration_ingestion_replay_and_compare():
    engine = make_engine(os.environ["AGENTREPLAY_TEST_POSTGRES"])
    with TestClient(create_app(engine)) as client:
        source = client.post("/v1/demo", json={"fail": True})
        assert source.status_code == 201
        run_id = source.json()["id"]
        replay = client.post(f"/v1/runs/{run_id}/replays", json={"mode": "reexecution"})
        assert replay.status_code == 201
        assert replay.json()["replay_report"]["faithful"]
        assert client.get(f"/v1/runs/{run_id}").status_code == 200
        assert (
            client.get(f"/v1/compare?left={run_id}&right={replay.json()['id']}").status_code == 200
        )
