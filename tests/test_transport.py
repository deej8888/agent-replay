import threading

import httpx
from agentreplay import BufferedHTTPTransport


def test_buffered_export_flushes_on_close(recorded, monkeypatch):
    exported = []
    main_thread = threading.get_ident()
    client_class = httpx.Client

    def handle(request):
        assert threading.get_ident() != main_thread
        assert request.headers["X-API-Key"] == "local-test-key"
        exported.append(request)
        return httpx.Response(201, json={"id": str(recorded.id)})

    monkeypatch.setattr(
        httpx, "Client", lambda **kw: client_class(transport=httpx.MockTransport(handle), **kw)
    )
    with BufferedHTTPTransport(api_key="local-test-key") as transport:
        transport.submit(recorded)
    assert len(exported) == 1 and transport.failed == 0
    transport.submit(recorded)
    assert transport.dropped == 1


def test_failed_export_does_not_raise_into_application(recorded, monkeypatch):
    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kw: client_class(
            transport=httpx.MockTransport(lambda request: httpx.Response(503)), **kw
        ),
    )
    with BufferedHTTPTransport() as transport:
        transport.submit(recorded)
    assert transport.failed == 1
