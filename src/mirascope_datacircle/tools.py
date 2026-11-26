"""Four Mirascope tools on Datacircle's open API, https://api.datacircle.dev/v1: no key, no account.

Each is an llm.tool, one call of the API: llm.call(..., tools=datacircle_tools) shows the model its name, its docstring
and its parameters, and response.execute_tools() runs the ones the model asks for. Each makes one HTTPS GET and gives
the model the API's answer as JSON. A refusal (an unknown slug, a number out of range, the API out of reach) is a
DatacircleError, whose words Mirascope gives the model as the tool's output, so the model can call again.

Each optional parameter takes null, as OpenAI's strict tools send every parameter. Its description is its line under
Args, one line each, as Mirascope reads it. The tools here are for a sync call; mirascope_datacircle.aio has the same
four for an async one.
"""

from typing import Any, Literal, Optional

from mirascope import llm

from mirascope_datacircle import _api


@llm.tool
def datacircle_list_apis(query: Optional[str] = None, limit: Optional[int] = None) -> dict[str, Any]:
    """Lists the GTM APIs on Datacircle's sheet (https://datacircle.dev), with each API's slug, how many plans and providers it has and its best plan. Use it first to find an API's slug. Gives total, the APIs found, and apis, up to limit of them.

    Args:
        query: Words of the API's name or slug, like 'email' or 'linkedin profile': the APIs that hold the most of them come first. null for the sheet's order.
        limit: How many APIs to give, 1 to 200. null for 20.
    """
    return _api.get(_api.list_apis(query, limit))


@llm.tool
def datacircle_best_plans(slug: str, limit: Optional[int] = None) -> dict[str, Any]:
    """Gives an API's plans best first by their score out of 100 on Datacircle's benchmark (https://datacircle.dev), each with its rank, provider, plan, $ per 1,000 calls and its page: the best providers of an API. perThousand is a plan's price of 1,000 items in dollars, pay the plan's whole price in its currency.

    Args:
        slug: The API's slug, like 'email-finder' or 'linkedin-profile'. datacircle_list_apis gives every slug.
        limit: How many plans to give, 1 to 50. null for 10.
    """
    return _api.get(_api.best_plans(slug, limit))


@llm.tool
def datacircle_search_plans(api: Optional[str] = None, query: Optional[str] = None,
                            sort: Optional[Literal["score", "provider", "price"]] = None,
                            limit: Optional[int] = None, offset: Optional[int] = None) -> dict[str, Any]:
    """Searches every plan on Datacircle's sheet (https://datacircle.dev), or one API's, by provider or plan name, sorted by score, provider or price. Gives total, offset and up to limit plans. perThousand is a plan's price of 1,000 items in dollars, pay the plan's whole price in its currency.

    Args:
        api: Only this API's plans: its name or slug, like 'email-finder'. A provider's name goes in query, never here. null for every API.
        query: Words that must all appear in the provider's or plan's name, like 'bright data'. null for every plan.
        sort: score (best first), provider (A to Z) or price ($ per 1,000, lowest first). null for score.
        limit: How many plans to give, 1 to 50. null for 10.
        offset: How many found plans to skip first. null for 0.
    """
    return _api.get(_api.search_plans(api, query, sort, limit, offset))


@llm.tool
def datacircle_provider(slug: str) -> dict[str, Any]:
    """Gives each API one provider sells and its rank on each on Datacircle's benchmark (https://datacircle.dev), with its best plan there.

    Args:
        slug: The provider's slug, like 'bright-data', or its name, like 'Bright Data': the name is made a slug.
    """
    return _api.get(_api.provider(slug))


datacircle_tools = [datacircle_list_apis, datacircle_best_plans, datacircle_search_plans, datacircle_provider]
