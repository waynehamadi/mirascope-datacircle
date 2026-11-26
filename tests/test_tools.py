"""Offline tests: the tools against a local stand-in for the API on 127.0.0.1, by each tool's own call and by
Mirascope's execute() of a model's tool call, sync and async."""

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from mirascope import llm

import mirascope_datacircle as dc
from mirascope_datacircle import _api, aio

PLAN = {"api": "Employee email", "rank": 1, "provider": "Hunter", "plan": "Starter", "score": 80.1, "perThousand": 4.9,
        "page": "https://datacircle.dev/x", "terms": "long", "aggregators": ["a"]}
BRIEF = {key: value for key, value in PLAN.items() if key not in ("terms", "aggregators")}
SEEN = []
BUSY = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def reply(self, status, body, headers=None):
        data = json.dumps(body).encode()
        self.send_response(status)
        for key, value in {"Content-Type": "application/json", "Content-Length": str(len(data)), **(headers or {})}.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(url.query).items()}
        SEEN.append((url.path, query, self.headers.get("User-Agent")))
        if url.path == "/v1/plans" and query.get("query") == "busy" and len(BUSY) % 2 == 0:
            BUSY.append(1)
            return self.reply(429, {"error": "slow down"}, {"Retry-After": "1"})
        if url.path == "/v1/plans" and query.get("query") == "busy":
            BUSY.append(1)
        if url.path == "/v1/apis":
            return self.reply(200, [{"api": "Employee email", "slug": "email-finder", "plans": 9, "providers": 3, "extra": 1},
                                    {"api": "Employee profile", "slug": "linkedin-profile", "plans": 4, "providers": 2}])
        if url.path == "/v1/apis/email-finder/best":
            return self.reply(200, {"api": "Employee email", "slug": "email-finder", "total": 1, "plans": [PLAN]})
        if url.path.startswith("/v1/apis/"):
            return self.reply(404, {"error": "no API has the slug nope", "slugs": ["email-finder", "linkedin-profile"]})
        if url.path == "/v1/plans" and query.get("query") == "down":
            return self.reply(503, {"error": "down for a minute"})
        if url.path == "/v1/plans":
            return self.reply(200, {"total": 1, "offset": 0, "plans": [PLAN]})
        if url.path == "/v1/providers/bright-data":
            return self.reply(200, {"provider": "Bright Data", "slug": "bright-data", "apis": [
                {"api": "Employee email", "slug": "email-finder", "rank": 4, "bestPage": "https://datacircle.dev/b",
                 "plans": [{**PLAN, "rank": 9, "plan": "Big"}, {**PLAN, "rank": 4, "plan": "Small"}, {**PLAN, "rank": None}]}]})
        return self.reply(404, {"error": "no provider has the slug " + url.path.rsplit("/", 1)[-1]})


@pytest.fixture(autouse=True)
def stand_in(monkeypatch):
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(_api, "BASE_URL", f"http://127.0.0.1:{server.server_address[1]}/v1")
    SEEN.clear()
    yield
    server.shutdown()


def call(name, arguments):
    return llm.ToolCall(id="call_1", name=name, args=json.dumps(arguments))


def test_the_tools_mirascope_sees():
    assert [tool.name for tool in dc.datacircle_tools] == ["datacircle_list_apis", "datacircle_best_plans",
                                                         "datacircle_search_plans", "datacircle_provider"]
    for tool, twin in zip(dc.datacircle_tools, dc.async_datacircle_tools):
        assert isinstance(tool, llm.Tool) and isinstance(twin, llm.AsyncTool)
        assert (twin.name, twin.description, twin.parameters) == (tool.name, tool.description, tool.parameters)
        assert "https://datacircle.dev" in tool.description
        assert tool.parameters.additionalProperties is False
        for name, schema in tool.parameters.properties.items():
            assert schema.get("description") and "\n" not in schema["description"], (tool.name, name)
            assert ({"type": "null"} in schema.get("anyOf", [])) == (name not in tool.parameters.required)
    assert dc.datacircle_best_plans.parameters.required == ["slug"]
    assert dc.datacircle_provider.parameters.required == ["slug"]
    sort = dc.datacircle_search_plans.parameters.properties["sort"]["anyOf"][0]
    assert sort["enum"] == ["score", "provider", "price"]
    llm.Toolkit([*dc.datacircle_tools])  # no two share a name
    assert dc.__version__ in _api.USER_AGENT


def test_each_tool_by_its_own_call():
    found = dc.datacircle_list_apis(query="profile", limit=1)
    assert found == {"total": 1, "apis": [{"api": "Employee profile", "slug": "linkedin-profile", "plans": 4, "providers": 2}]}
    assert dc.datacircle_list_apis()["total"] == 2
    best = dc.datacircle_best_plans("Email Finder", 3)
    assert best["plans"] == [BRIEF] and best["slug"] == "email-finder"
    assert SEEN[-1][:2] == ("/v1/apis/email-finder/best", {"limit": "3"})
    assert dc.datacircle_search_plans(query="hunter", sort="Price", limit="5", offset=0)["plans"] == [BRIEF]
    assert SEEN[-1][1] == {"query": "hunter", "sort": "price", "limit": "5", "offset": "0"}
    dc.datacircle_search_plans(api=None, query=None, sort=None, limit=None, offset=None)
    assert SEEN[-1][1] == {}
    provider = dc.datacircle_provider("Bright Data")
    assert provider["apis"][0]["plans"] == 3 and provider["apis"][0]["best"]["plan"] == "Small"
    assert all(agent == _api.USER_AGENT for _, _, agent in SEEN)


def test_refusals_in_words():
    with pytest.raises(dc.DatacircleError) as refused:
        dc.datacircle_best_plans("nope")
    assert refused.value.status == 404 and "no API has the slug nope; the slugs: email-finder, linkedin-profile" in str(refused.value)
    with pytest.raises(dc.DatacircleError) as refused:
        dc.datacircle_search_plans(query="down")
    assert refused.value.status == 503 and refused.value.retryable and "down for a minute" in str(refused.value)
    sent = len(SEEN)
    for bad in [lambda: dc.datacircle_best_plans("email-finder", 0), lambda: dc.datacircle_best_plans("email-finder", 2.5),
                lambda: dc.datacircle_search_plans(sort="cheap"), lambda: dc.datacircle_search_plans(offset=-1),
                lambda: dc.datacircle_best_plans(""), lambda: dc.datacircle_provider("  "),
                lambda: dc.datacircle_list_apis(limit=True)]:
        with pytest.raises(dc.DatacircleError):
            bad()
    assert len(SEEN) == sent  # no call made


def test_waits_once_on_429():
    assert dc.datacircle_search_plans(query="busy")["total"] == 1
    assert [query.get("query") for _, query, _ in SEEN] == ["busy", "busy"]
    assert asyncio.run(aio.datacircle_search_plans(query="busy"))["total"] == 1


def test_unreachable(monkeypatch):
    monkeypatch.setattr(_api, "BASE_URL", "http://127.0.0.1:9/v1")
    with pytest.raises(dc.DatacircleError) as refused:
        dc.datacircle_list_apis()
    assert refused.value.retryable and "could not be reached" in str(refused.value)


def test_execute_a_models_call():
    toolkit = llm.Toolkit(dc.datacircle_tools)
    output = toolkit.execute(call("datacircle_best_plans", {"slug": "email-finder", "limit": None}))
    assert output.error is None and output.result["plans"] == [BRIEF] and output.name == "datacircle_best_plans"
    output = toolkit.execute(call("datacircle_search_plans", {"api": None, "query": None, "sort": "price", "limit": 2, "offset": None}))
    assert output.error is None and output.result["total"] == 1
    output = toolkit.execute(call("datacircle_best_plans", {"slug": "nope"}))
    assert output.error is not None and "no API has the slug nope" in output.result


def test_async_tools():
    async def run():
        toolkit = llm.AsyncToolkit(dc.async_datacircle_tools)
        outputs = await asyncio.gather(
            toolkit.execute(call("datacircle_list_apis", {"query": "email", "limit": 1})),
            toolkit.execute(call("datacircle_provider", {"slug": "bright-data"})),
            toolkit.execute(call("datacircle_best_plans", {"slug": "nope", "limit": None})))
        assert outputs[0].result["apis"][0]["slug"] == "email-finder"
        assert outputs[1].result["slug"] == "bright-data"
        assert outputs[2].error is not None and "the slugs: email-finder" in outputs[2].result
        assert (await aio.datacircle_best_plans("email-finder"))["plans"] == [BRIEF]
    asyncio.run(run())
