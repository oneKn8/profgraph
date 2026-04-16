"""Grade distribution client using UTD Nebula Trends API."""

from __future__ import annotations

import httpx

from .cache import TTLCache
from .models import GradeDistribution

NEBULA_URL = "https://trends.utdnebula.com/api/grades"

# Nebula grade_distribution array: 14 elements in this order
GRADE_KEYS = [
    "a_plus", "a", "a_minus",
    "b_plus", "b", "b_minus",
    "c_plus", "c", "c_minus",
    "d_plus", "d", "d_minus",
    "f", "w",
]


class GradesClient:
    def __init__(self, cache: TTLCache):
        self._cache = cache

    async def get_distribution(
        self,
        prefix: str,
        number: str,
        professor: str | None = None,
    ) -> list[GradeDistribution]:
        cache_key = f"grades:{prefix}:{number}:{professor}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {"prefix": prefix, "number": number}
        if professor:
            params["professor"] = professor

        async with httpx.AsyncClient() as client:
            resp = await client.get(NEBULA_URL, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()

        entries = data.get("data", [])
        results = []
        for entry in entries:
            arr = entry.get("grade_distribution", [])
            if len(arr) < 14:
                continue
            kwargs = {GRADE_KEYS[i]: arr[i] for i in range(14)}
            kwargs["semester"] = entry["_id"]
            results.append(GradeDistribution(**kwargs))

        results.sort(key=lambda d: d.semester, reverse=True)
        self._cache.set(cache_key, results)
        return results
