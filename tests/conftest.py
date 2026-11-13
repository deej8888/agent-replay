import pytest
from agentreplay import MemoryTransport, Tracer
from agentreplay_api.database import Base, make_engine
from agentreplay_api.main import create_app
from agentreplay_examples.agent import shopping_agent
from fastapi.testclient import TestClient


@pytest.fixture
def recorded():
    transport = MemoryTransport()
    with Tracer(transport).use():
        shopping_agent("Find a keyboard")
    return transport.runs[0]


@pytest.fixture
def client():
    engine = make_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with TestClient(create_app(engine, migrate=False)) as client:
        yield client
