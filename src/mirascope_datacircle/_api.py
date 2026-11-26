"""One HTTPS GET to Datacircle's open API (https://api.datacircle.dev/v1), no key, and what its answers are cut to for a model.

Each tool builds its request here (path and query, its arguments checked first), sends it with httpx, sync or async, and
gives the model the answer shape() cuts it to. A refusal is a DatacircleError in the API's words.
"""

from __future__ import annotations

import asyncio
import math
import re
import time
import unicodedata
import urllib.parse
from collections.abc import Callable
from typing import Any

import httpx

BASE_URL = "https://api.datacircle.dev/v1"
TIMEOUT = 30.0
USER_AGENT = "mirascope-datacircle/0.1.0"

# A plan holds about 90 keys (its terms of use, its aggregators...): the tools keep the ones that choose a plan, the rest is on its page.
PLAN_KEYS = ["api", "rank", "provider", "plan", "score", "perThousand", "notFoundPerThousand", "billing", "pay",
             "currency", "units", "unit", "strengths", "latencyMs", "page", "pricingPage", "docs"]
API_KEYS = ["api", "slug", "plans", "providers", "best", "bestPage", "sheetPage"]


class DatacircleError(Exception):
    """The API's refusal in its own words, why it could not be reached, or an argument it can't take. Mirascope gives
    the model its words as the tool's output, so the model can call again. status is the API's HTTP status, None when
    it gave none; retryable, whether the same call may be answered later (the API out of reach, busy or failing)."""

    def __init__(self, message: str, status: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


def brief(item: dict[str, Any], keys: list[str] = PLAN_KEYS) -> dict[str, Any]:
    return {key: item[key] for key in keys if item.get(key) is not None}


def slug(value: Any) -> str:
    """The API's rule for a slug: the name in lowercase letters and digits, the rest a hyphen."""
    plain = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def whole(name: str, value: Any, low: int, high: int | None = None) -> int | None:
    """A whole number from low to high, or None when left out: a model may send one as text."""
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = float("nan")
    if isinstance(value, bool) or not math.isfinite(number) or number != int(number):
        raise DatacircleError(f"{name} must be a whole number, not {value!r}")
    if number < low or (high is not None and number > high):
        raise DatacircleError(f"{name} must be from {low} to {high}, not {int(number)}" if high is not None
                              else f"{name} must be {low} or more, not {int(number)}")
    return int(number)


def text(value: Any) -> str | None:
    """A text argument as the API takes it: a number made text, null and blank left out."""
    return None if value is None or str(value).strip() == "" else str(value)


def _best(plans: Any) -> dict[str, Any] | None:
    """A provider's best plan on an API: its lowest rank, a plan with no score having none."""
    ranked = sorted(plans, key=lambda plan: plan.get("rank") if isinstance(plan.get("rank"), (int, float)) else float("inf"))
    return brief(ranked[0], ["plan", "score", "perThousand", "page"]) if ranked else None


# Each request: (path, query, shape), shape making the API's JSON what the model gets.
Request = tuple[str, dict[str, Any], Callable[[Any], dict[str, Any]]]


def list_apis(query: Any = None, limit: Any = None) -> Request:
    count = whole("limit", limit, 1, 200) or 20
    words = [word for word in str(text(query) or "").lower().replace("-", " ").split() if word]

    def shape(apis: Any) -> dict[str, Any]:
        held = []
        for index, api in enumerate(apis):
            name = f"{api.get('api', '')} {str(api.get('slug', '')).replace('-', ' ')}".lower()
            matched = sum(word in name for word in words)
            if matched or not words:
                held.append((-matched, index, api))
        found = [brief(api, API_KEYS) for _, _, api in sorted(held, key=lambda h: h[:2])]
        return {"total": len(found), "apis": found[:count]}
    return "/apis", {}, shape


def _plans(answer: Any) -> dict[str, Any]:
    return {**answer, "plans": [brief(plan) for plan in answer.get("plans") or []]}


def best_plans(api_slug: Any = None, limit: Any = None) -> Request:
    made = slug(api_slug)
    if not made:
        raise DatacircleError("Give an API's slug, like 'email-finder'. datacircle_list_apis gives every slug.")
    return f"/apis/{urllib.parse.quote(made)}/best", {"limit": whole("limit", limit, 1, 50)}, _plans


def search_plans(api: Any = None, query: Any = None, sort: Any = None, limit: Any = None, offset: Any = None) -> Request:
    order = text(sort)
    order = order.strip().lower() if order is not None else None
    if order is not None and order not in ("score", "provider", "price"):
        raise DatacircleError(f"sort must be score, provider or price, not {sort!r}")
    params = {"api": text(api), "query": text(query), "sort": order, "limit": whole("limit", limit, 1, 50),
              "offset": whole("offset", offset, 0)}
    return "/plans", params, _plans


def provider(provider_slug: Any = None) -> Request:
    made = slug(provider_slug)
    if not made:
        raise DatacircleError("Give a provider's slug or name, like 'bright-data' or 'Bright Data'")

    def shape(answer: Any) -> dict[str, Any]:
        apis = [{**brief(entry, ["api", "slug", "rank", "bestPage"]), "plans": len(entry.get("plans") or []),
                 "best": _best(entry.get("plans") or [])} for entry in answer.get("apis") or []]
        return {**answer, "apis": apis}
    return f"/providers/{urllib.parse.quote(made)}", {}, shape


def _url(path: str, params: dict[str, Any]) -> str:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    return f"{BASE_URL.rstrip('/')}{path}" + (f"?{query}" if query else "")


_HEADERS = {"Accept": "application/json", "User-Agent": USER_AGENT}


def _words(answer: httpx.Response) -> str:
    """A refusal's words: the API's error, with every slug when the slug was unknown."""
    try:
        parsed = answer.json()
        if parsed.get("slugs"):
            return f"{parsed['error']}; the slugs: {', '.join(parsed['slugs'])}"
        return str(parsed.get("error", answer.text))
    except (ValueError, KeyError, TypeError, AttributeError):
        return answer.text


def _wait(answer: httpx.Response) -> float:
    try:
        return min(max(int(answer.headers.get("Retry-After") or 30), 1), 60)
    except ValueError:
        return 30


def _read(answer: httpx.Response) -> Any:
    if answer.status_code == 429:
        raise DatacircleError("Datacircle's API answered 429 twice: wait a minute and call again", 429, True)
    if answer.status_code >= 400:
        raise DatacircleError(f"Datacircle's API answered {answer.status_code}: {_words(answer)[:3000]}",
                              answer.status_code, answer.status_code >= 500)
    try:
        return answer.json()
    except ValueError as error:
        raise DatacircleError(f"Datacircle's API gave no JSON: {error}") from None


def _unreached(error: httpx.HTTPError) -> DatacircleError:
    return DatacircleError(f"Datacircle's API could not be reached: {error!r}", retryable=True)


def get(request: Request) -> dict[str, Any]:
    """The request's answer as the model gets it, or a DatacircleError with the API's words: waits once on a 429."""
    path, params, shape = request
    try:
        with httpx.Client(timeout=TIMEOUT, headers=_HEADERS) as client:
            answer = client.get(_url(path, params))
            if answer.status_code == 429:
                time.sleep(_wait(answer))
                answer = client.get(_url(path, params))
    except httpx.HTTPError as error:
        raise _unreached(error) from None
    return shape(_read(answer))


async def get_async(request: Request) -> dict[str, Any]:
    """get() for an async call: the same answer, the wait on a 429 not holding the event loop."""
    path, params, shape = request
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, headers=_HEADERS) as client:
            answer = await client.get(_url(path, params))
            if answer.status_code == 429:
                await asyncio.sleep(_wait(answer))
                answer = await client.get(_url(path, params))
    except httpx.HTTPError as error:
        raise _unreached(error) from None
    return shape(_read(answer))
