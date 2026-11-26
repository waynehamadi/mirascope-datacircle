"""The four tools of mirascope_datacircle.tools for an async call (an async def under llm.call): the same names,
docstrings, parameters and answers, as llm.AsyncTool, each call awaited."""

from typing import Any, Literal, Optional

from mirascope import llm

from mirascope_datacircle import _api, tools


def _doc_of(twin: Any) -> Any:
    """Gives a function its sync twin's docstring before llm.tool reads it."""
    def give(fn: Any) -> Any:
        fn.__doc__ = twin.fn.__doc__
        return fn
    return give


@llm.tool
@_doc_of(tools.datacircle_list_apis)
async def datacircle_list_apis(query: Optional[str] = None, limit: Optional[int] = None) -> dict[str, Any]:
    return await _api.get_async(_api.list_apis(query, limit))


@llm.tool
@_doc_of(tools.datacircle_best_plans)
async def datacircle_best_plans(slug: str, limit: Optional[int] = None) -> dict[str, Any]:
    return await _api.get_async(_api.best_plans(slug, limit))


@llm.tool
@_doc_of(tools.datacircle_search_plans)
async def datacircle_search_plans(api: Optional[str] = None, query: Optional[str] = None,
                                  sort: Optional[Literal["score", "provider", "price"]] = None,
                                  limit: Optional[int] = None, offset: Optional[int] = None) -> dict[str, Any]:
    return await _api.get_async(_api.search_plans(api, query, sort, limit, offset))


@llm.tool
@_doc_of(tools.datacircle_provider)
async def datacircle_provider(slug: str) -> dict[str, Any]:
    return await _api.get_async(_api.provider(slug))


datacircle_tools = [datacircle_list_apis, datacircle_best_plans, datacircle_search_plans, datacircle_provider]
