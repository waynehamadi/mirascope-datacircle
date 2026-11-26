# mirascope-datacircle

Find the best GTM APIs. We benchmark all the GTM APIs and we put the results on our website.

Our website: https://datacircle.dev

This package gives [Mirascope](https://github.com/Mirascope/mirascope) four tools that call Datacircle's public API, https://api.datacircle.dev/v1. You need no key and no account.

| Tool | Gives | Call |
| --- | --- | --- |
| `datacircle_list_apis` | Every GTM API on Datacircle, with the API's slug, number of plans, number of providers and best plan | `GET /apis` |
| `datacircle_best_plans` | One API's plans, sorted by score out of 100, best first. Each plan comes with a rank and a price per 1,000 calls | `GET /apis/{slug}/best` |
| `datacircle_search_plans` | Plans that match a provider or plan name, on all APIs or on one API. You can sort them by score, provider or price | `GET /plans` |
| `datacircle_provider` | The APIs a provider sells, and the provider's rank on each API | `GET /providers/{slug}` |

## Install

```bash
pip install mirascope-datacircle
```

The package needs Mirascope 2.0 or later and Python 3.10 or later. Also install Mirascope with the extra for your provider, for example `pip install "mirascope[openai]"`.

## Give the tools to a call

```python
from mirascope import llm
from mirascope_datacircle import datacircle_tools

@llm.call("openai/gpt-5-mini", tools=datacircle_tools)
def ask(question: str) -> str:
    return question

response = ask("Which email finder API is best for under $5 per 1,000?")
while response.tool_calls:
    response = response.resume(response.execute_tools())
print(response.text())
```

The model picks a tool. `response.execute_tools()` runs every tool call in the response. `response.resume()` gives the model the results.

To add your own tools, list ours and yours together: `tools=[*datacircle_tools, my_tool]`. To give the model only two of our tools, list the two: `tools=[datacircle_best_plans, datacircle_search_plans]`.

To stream, call `ask.stream(...)` and read the whole stream. Then call `execute_tools()` and `resume()`. You can also pass the tools to a call that takes an `llm.Context`.

## Async calls

For an async call, use `async_datacircle_tools`. The four async tools have the same names as the sync tools. You await each step:

```python
import asyncio

from mirascope import llm
from mirascope_datacircle import async_datacircle_tools

@llm.call("openai/gpt-5-mini", tools=async_datacircle_tools)
async def ask(question: str) -> str:
    return question

async def main():
    response = await ask("Who are the best LinkedIn profile API providers?")
    while response.tool_calls:
        response = await response.resume(await response.execute_tools())
    print(response.text())

asyncio.run(main())
```

You can also import each async tool by name from `mirascope_datacircle.aio`.

## Call a tool yourself

```python
from mirascope_datacircle import datacircle_best_plans

result = datacircle_best_plans("email-finder", limit=3)
print(result["plans"][0])
```

Each tool returns our API's answer as a Python dict.

## Tool output for the model

Each plan comes with a rank, provider, plan, score, price per 1,000 (`perThousand`, in dollars) and a page on datacircle.dev. That page lists every field.

You can give a provider's name in place of a slug. The tool turns `Bright Data` into `bright-data`.

The tool raises a `DatacircleError` with the API's error message for an unknown slug. Mirascope gives the model the error message as the tool's output. The error message for an unknown API slug lists every valid slug. The model can then pick a valid slug and call the tool again. The tool checks each value from the model before the API call. A number out of range gets the model an error and no API call.

The tools work with OpenAI's strict tool calls. In strict mode the model sends every parameter, so each optional parameter takes `null`.

## Network

Each tool makes one HTTPS GET request to https://api.datacircle.dev/v1 and no other network calls. The request holds only the tool's input. The API takes up to 60 calls a minute from one IP address. If the API says to wait, the tool waits up to a minute. The tool waits at most once per call. All plans are in one file at https://datacircle.dev/datacircle.json.

## Links

- Datacircle: https://datacircle.dev
- The API: https://datacircle.dev/api
- The API's spec: https://api.datacircle.dev/v1/openapi.json
- What each key means: https://datacircle.dev/fields

MIT license.
