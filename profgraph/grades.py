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


class GradesError(Exception):
    """Raised when grade data fetching fails."""


class GradesClient:
    def __init__(self, cache: TTLCache):
        self._cache = cache

    async def get_distribution(
        self,
        prefix: str,
        number: str,
        professor: str | None = None,
        semester: str | None = None,
    ) -> list[GradeDistribution]:
        cache_key = f"grades:{prefix}:{number}:{professor}:{semester}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        params: dict[str, str] = {"prefix": prefix, "number": number}
        if professor:
            params["professor"] = professor

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(NEBULA_URL, params=params, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as e:
            raise GradesError(f"Nebula API error: HTTP {e.response.status_code}") from e
        except httpx.RequestError as e:
            raise GradesError(f"Network error reaching Nebula: {e}") from e

        entries = data.get("data", [])
        results = []
        for entry in entries:
            sem_id = entry.get("_id")
            if not sem_id:
                continue
            arr = entry.get("grade_distribution", [])
            if len(arr) < 14:
                continue
            kwargs = {GRADE_KEYS[i]: arr[i] for i in range(14)}
            kwargs["semester"] = sem_id
            results.append(GradeDistribution(**kwargs))

        # Filter by semester if requested
        if semester:
            sem_upper = semester.upper()
            results = [d for d in results if d.semester.upper() == sem_upper]

        results.sort(key=lambda d: d.semester, reverse=True)
        self._cache.set(cache_key, results)
        return results
