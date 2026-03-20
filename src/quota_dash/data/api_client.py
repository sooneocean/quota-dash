from __future__ import annotations

import httpx


async def fetch_openai_usage(api_key: str) -> dict | None:
    """Try OpenAI Administration API for org usage.

    Returns {"usage_usd": float} on success, None on failure.
    Requires an admin API key with org-level permissions.
    """
    if not api_key:
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openai.com/v1/organization/usage",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return None

            data = resp.json()
            results = data.get("data", [{}])[0].get("results", [])
            total = sum(
                r.get("amount", {}).get("value", 0.0)
                for r in results
            )
            return {"usage_usd": total}
    except (httpx.HTTPError, KeyError, IndexError, ValueError):
        return None
