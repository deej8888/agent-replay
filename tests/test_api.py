from uuid import uuid4

from agentreplay import Run


def test_ingestion_tree_span_and_filters(client, recorded):
    payload = recorded.model_dump(mode="json")
    assert client.post("/v1/runs", json=payload).status_code == 201
    assert client.post("/v1/runs", json=payload).status_code == 409
    response = client.get(f"/v1/runs/{recorded.id}")
    assert Run.model_validate(response.json()) == recorded
    span = recorded.spans[1]
    assert client.get(f"/v1/runs/{recorded.id}/spans/{span.id}").json()["name"] == "search_catalog"
    assert client.get(f"/v1/runs/{uuid4()}/spans/{span.id}").status_code == 404
    assert (
        client.get("/v1/runs?q=shopping&status=success&model=deterministic-fake-v1").json()["total"]
        == 1
    )
    assert client.get("/v1/runs?status=error").json()["total"] == 0
    assert client.get("/v1/runs?limit=1&offset=1").json()["items"] == []
    assert client.get("/v1/runs?limit=101").status_code == 422


def test_demo_reexecute_failure_and_divergence(client):
    source = client.post("/v1/demo", json={"fail": True}).json()
    assert source["status"] == "error"
    replay = client.post(f"/v1/runs/{source['id']}/replays", json={"mode": "reexecution"})
    assert replay.status_code == 201
    assert replay.json()["status"] == "error"
    assert replay.json()["replay_report"]["faithful"]
    diverged = client.post(
        f"/v1/runs/{source['id']}/replays",
        json={"mode": "reexecution", "simulate_divergence": True},
    ).json()
    assert not diverged["replay_report"]["faithful"]
    assert diverged["replay_report"]["missing_calls"]
    assert diverged["error"]["type"] == "ReplayDivergence"


def test_playback_is_distinct_and_preserves_original_times(client, recorded):
    client.post("/v1/runs", json=recorded.model_dump(mode="json"))
    replay = client.post(f"/v1/runs/{recorded.id}/replays", json={"mode": "playback"}).json()
    assert replay["mode"] == "playback"
    assert replay["id"] != str(recorded.id)
    assert replay["source_run_id"] == str(recorded.id)
    assert replay["started_at"] == recorded.model_dump(mode="json")["started_at"]
    assert {s["id"] for s in replay["spans"]}.isdisjoint({str(s.id) for s in recorded.spans})


def test_comparison_aligns_semantic_paths(client):
    a = client.post("/v1/demo", json={}).json()
    b = client.post("/v1/demo", json={"fail": True}).json()
    diff = client.get(f"/v1/compare?left={a['id']}&right={b['id']}").json()
    assert len(diff["changes"]) == 4
    assert any(c["change"] == "removed" and "compose_answer" in c["path"] for c in diff["changes"])
    assert any("error" in c["fields"] for c in diff["changes"])


def test_invalid_trees_and_status_are_rejected(client, recorded):
    payload = recorded.model_dump(mode="json")
    payload["spans"][1]["parent_id"] = str(uuid4())
    assert client.post("/v1/runs", json=payload).status_code == 422
    payload = recorded.model_dump(mode="json")
    payload["spans"][1]["sequence"] = 0
    assert client.post("/v1/runs", json=payload).status_code == 422
    payload = recorded.model_dump(mode="json")
    payload["status"] = "error"
    assert client.post("/v1/runs", json=payload).status_code == 422


def test_missing_records_and_bad_ids(client):
    assert client.get(f"/v1/runs/{uuid4()}").status_code == 404
    assert client.get("/v1/runs/not-a-uuid").status_code == 422


def test_server_redacts_untrusted_ingestion(client, recorded):
    payload = recorded.model_dump(mode="json")
    payload["input"] = {"password": "private", "text": "someone@example.com"}
    payload["spans"][0]["metadata"] = {"api_key": "secret"}
    response = client.post("/v1/runs", json=payload)
    assert response.status_code == 201
    assert "private" not in response.text and "someone@example.com" not in response.text
    assert response.json()["spans"][0]["metadata"]["api_key"] == "[REDACTED]"


def test_body_size_limit(client):
    response = client.post(
        "/v1/runs", content=b" " * 2_097_153, headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413


def test_optional_api_key(client, monkeypatch):
    monkeypatch.setenv("AGENTREPLAY_API_KEY", "test-key")
    assert client.get("/v1/runs").status_code == 401
    assert client.get("/health").status_code == 200
    assert client.get("/v1/runs", headers={"X-API-Key": "test-key"}).status_code == 200


def test_validation_errors_never_echo_raw_payloads(client):
    response = client.post("/v1/runs", json={"api_key": "do-not-reflect-this"})
    assert response.status_code == 422
    assert "do-not-reflect-this" not in response.text
