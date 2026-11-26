"""Mirascope tools for Datacircle's open API (https://api.datacircle.dev/v1): find the best GTM APIs, no key.

datacircle_tools, for llm.call's tools beside an app's own, and each tool by its name; async_datacircle_tools for an
async call (mirascope_datacircle.aio, the same names). See https://datacircle.dev.
"""

from mirascope_datacircle._api import DatacircleError
from mirascope_datacircle.aio import datacircle_tools as async_datacircle_tools
from mirascope_datacircle.tools import (
    datacircle_best_plans,
    datacircle_list_apis,
    datacircle_provider,
    datacircle_search_plans,
    datacircle_tools,
)

__version__ = "0.1.0"
__all__ = [
    "DatacircleError",
    "async_datacircle_tools",
    "datacircle_best_plans",
    "datacircle_list_apis",
    "datacircle_provider",
    "datacircle_search_plans",
    "datacircle_tools",
]
