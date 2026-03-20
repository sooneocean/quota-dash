from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def fetch_openai_usage(api_key: str) -> dict | None:
    """Try OpenAI Administration API for org usage.

    Returns {"usage_usd": float} on success, None on failure.
    Requires an admin API key with org-level permissions.
    """
    if not api_key:
        logger.debug("No API key provided, skipping OpenAI usage fetch")
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openai.com/v1/organization/usage",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code != 200:
                logger.warning("OpenAI usage API returned %d", resp.status_code)
                return None

            data = resp.json()
            buckets = data.get("data", [])
            if not buckets:
                return {"usage_usd": 0.0}
            results = buckets[0].get("results", [])
            total = sum(
                r.get("amount", {}).get("value", 0.0)
                for r in results
            )
            return {"usage_usd": total}
    except httpx.TimeoutException:
        logger.warning("OpenAI usage API timed out")
        return None
    except httpx.HTTPError as exc:
        logger.warning("OpenAI usage API request failed: %s", exc)
        return None
    except (KeyError, IndexError, TypeError) as exc:
        logger.warning("OpenAI usage API response parse error: %s", exc)
        return None


async def check_openai_connection(api_key: str) -> tuple[bool, str]:
    """Test OpenAI API key validity. Returns (ok, message)."""
    if not api_key:
        return False, "No API key configured"

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                return True, "API key valid"
            elif resp.status_code == 401:
                return False, "Invalid API key"
            else:
                return False, f"Unexpected status {resp.status_code}"
    except httpx.TimeoutException:
        return False, "Connection timed out"
    except httpx.HTTPError as exc:
        return False, f"Connection failed: {exc}"
