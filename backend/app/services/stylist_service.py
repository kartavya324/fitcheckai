"""
AI Stylist — a Claude-powered chat that finds real clothing to buy.

The model (claude-opus-4-8) drives a `search_products` tool backed by Google
Shopping (via SerpAPI), so a request like "find me a hoodie under 2500" turns
into a real product search and a short styled recommendation with buy links.

Requires ANTHROPIC_API_KEY (the chat) and SERPAPI_KEY (the product search).
Both degrade with a clear message when unset rather than crashing.
"""
from __future__ import annotations

import json

import httpx

from app.config import Settings
from app.core.exceptions import AppError
from app.core.logging import get_logger

logger = get_logger(__name__)

MODEL = "claude-opus-4-8"

SYSTEM_PROMPT = (
    "You are FitCheck AI's personal fashion stylist. You help users find clothing "
    "and footwear to buy that fits their budget, occasion, and style.\n\n"
    "When the user wants to find or buy something (e.g. 'a black hoodie under 2500', "
    "'formal shoes for a wedding'), call the search_products tool with a concise "
    "query and any max_price they mention. Prices are in Indian Rupees (₹) unless "
    "the user says otherwise.\n\n"
    "After results come back, recommend 2–4 options conversationally — mention the "
    "price and one reason each fits their ask. Keep replies short, warm, and "
    "practical. Never invent products, prices, or links: only reference what "
    "search_products returned. If nothing is found, say so and suggest how to "
    "refine the search."
)

SEARCH_TOOL = {
    "name": "search_products",
    "description": (
        "Search online shopping listings for clothing or footwear to buy. Returns "
        "real products with title, price, store, image, and a buy link. Call this "
        "whenever the user wants to find or purchase an item."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search text, e.g. 'navy blue cotton hoodie men'",
            },
            "max_price": {
                "type": "number",
                "description": "Maximum price in the user's currency (INR unless stated). Optional.",
            },
        },
        "required": ["query"],
    },
}


def search_products(
    settings: Settings, query: str, max_price: float | None = None, limit: int = 6
) -> dict:
    """Google Shopping search via SerpAPI. Returns {'products': [...]} or {'error': ...}."""
    if not settings.serpapi_key:
        return {"error": "Product search is not configured. Set SERPAPI_KEY to enable it."}

    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": settings.serpapi_key,
        "gl": settings.shopping_locale,
        "hl": "en",
    }
    try:
        resp = httpx.get("https://serpapi.com/search.json", params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:  # network / API error — report, don't crash the chat
        logger.warning("SerpAPI search failed: %s", e)
        return {"error": f"Product search failed: {e}"}

    products = []
    for item in data.get("shopping_results", []):
        price = item.get("extracted_price")
        if max_price is not None and price is not None and price > max_price:
            continue
        products.append(
            {
                "title": item.get("title"),
                "price": price,
                "price_str": item.get("price"),
                "source": item.get("source"),
                "link": item.get("product_link") or item.get("link"),
                "thumbnail": item.get("thumbnail"),
            }
        )
        if len(products) >= limit:
            break

    return {"products": products}


class StylistService:
    """Runs the Claude tool-use loop for the stylist chat."""

    MAX_TOOL_TURNS = 4

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def chat(self, messages: list[dict]) -> dict:
        """
        messages: [{"role": "user"|"assistant", "content": "..."}] conversation so far.
        Returns {"reply": str, "products": [ ... ]}.
        """
        if not self._settings.anthropic_api_key:
            raise AppError(
                "AI stylist is not configured. Set ANTHROPIC_API_KEY to enable it.",
                code="CONFIG_ERROR",
                status_code=503,
            )

        import anthropic

        client = anthropic.Anthropic(api_key=self._settings.anthropic_api_key)
        convo: list[dict] = [
            {"role": m["role"], "content": m["content"]} for m in messages
        ]
        collected: list[dict] = []

        for _ in range(self.MAX_TOOL_TURNS):
            try:
                resp = client.messages.create(
                    model=MODEL,
                    max_tokens=1500,
                    system=SYSTEM_PROMPT,
                    thinking={"type": "adaptive"},
                    output_config={"effort": "medium"},
                    tools=[SEARCH_TOOL],
                    messages=convo,
                )
            except Exception as e:
                logger.exception("Claude request failed")
                raise AppError(
                    f"AI stylist request failed: {e}",
                    code="STYLIST_ERROR",
                    status_code=502,
                ) from e

            if resp.stop_reason == "tool_use":
                convo.append({"role": "assistant", "content": resp.content})
                tool_results = []
                for block in resp.content:
                    if block.type == "tool_use" and block.name == "search_products":
                        result = search_products(self._settings, **block.input)
                        if "products" in result:
                            collected.extend(result["products"])
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": json.dumps(result),
                            }
                        )
                convo.append({"role": "user", "content": tool_results})
                continue

            # Final answer
            reply = "".join(b.text for b in resp.content if b.type == "text")
            return {"reply": reply.strip(), "products": _dedupe(collected)}

        return {
            "reply": "I couldn't finish that search — please try rephrasing your request.",
            "products": _dedupe(collected),
        }


def _dedupe(products: list[dict]) -> list[dict]:
    seen, out = set(), []
    for p in products:
        key = p.get("link") or p.get("title")
        if key and key not in seen:
            seen.add(key)
            out.append(p)
    return out
