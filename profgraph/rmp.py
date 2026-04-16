"""RateMyProfessors GraphQL client."""

import httpx

from .cache import TTLCache
from .models import ProfessorProfile, ProfessorSummary

RMP_URL = "https://www.ratemyprofessors.com/graphql"
RMP_HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.ratemyprofessors.com/",
}

SCHOOL_IDS: dict[str, str] = {
    "utd": "U2Nob29sLTEyNzM=",
}

SCHOOL_ALIASES: dict[str, str] = {
    "ut dallas": "utd",
    "university of texas at dallas": "utd",
}

SEARCH_QUERY = """
query NewSearch($query: TeacherSearchQuery!) {
  newSearch {
    teachers(query: $query) {
      edges {
        node {
          id
          legacyId
          firstName
          lastName
          department
          avgRating
          avgDifficulty
          wouldTakeAgainPercent
          numRatings
        }
      }
    }
  }
}
"""

DETAIL_QUERY = """
query TeacherDetail($id: ID!) {
  node(id: $id) {
    ... on Teacher {
      id
      firstName
      lastName
      department
      avgRating
      avgDifficulty
      wouldTakeAgainPercent
      numRatings
      courseCodes { courseName courseCount }
      teacherRatingTags { tagName tagCount }
      ratings(first: 20) {
        edges {
          node {
            comment
            class
            date
            helpfulRating
            clarityRating
            difficultyRating
            wouldTakeAgain
            ratingTags
            grade
            isForOnlineClass
          }
        }
      }
    }
  }
}
"""


class RMPClient:
    def __init__(self, cache: TTLCache):
        self._cache = cache

    def _school_id(self, university: str) -> str:
        key = university.lower().strip()
        key = SCHOOL_ALIASES.get(key, key)
        if key not in SCHOOL_IDS:
            supported = ", ".join(sorted(SCHOOL_IDS))
            raise ValueError(
                f"University '{university}' not supported. Available: {supported}"
            )
        return SCHOOL_IDS[key]

    async def _post(self, query: str, variables: dict) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                RMP_URL,
                json={"query": query, "variables": variables},
                headers=RMP_HEADERS,
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                raise RuntimeError(f"GraphQL errors: {data['errors']}")
            return data

    async def search(
        self, university: str, query: str
    ) -> list[ProfessorSummary]:
        cache_key = f"rmp:search:{university}:{query.lower()}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        school_id = self._school_id(university)
        data = await self._post(
            SEARCH_QUERY,
            {"query": {"text": query, "schoolID": school_id, "fallback": True}},
        )

        edges = (
            data.get("data", {})
            .get("newSearch", {})
            .get("teachers", {})
            .get("edges", [])
        )
        results = []
        for edge in edges:
            n = edge.get("node")
            if not n:
                continue
            results.append(
                ProfessorSummary(
                    rmp_id=n["id"],
                    first_name=n["firstName"],
                    last_name=n["lastName"],
                    department=n.get("department", "Unknown"),
                    avg_rating=n.get("avgRating"),
                    avg_difficulty=n.get("avgDifficulty"),
                    would_take_again=n.get("wouldTakeAgainPercent"),
                    num_ratings=n.get("numRatings", 0),
                )
            )

        self._cache.set(cache_key, results)
        return results

    async def profile(self, rmp_id: str) -> ProfessorProfile:
        cache_key = f"rmp:profile:{rmp_id}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            return cached

        data = await self._post(DETAIL_QUERY, {"id": rmp_id})
        node = data.get("data", {}).get("node")
        if not node:
            raise ValueError(f"Professor not found: {rmp_id}")

        tags = sorted(
            node.get("teacherRatingTags", []),
            key=lambda t: t.get("tagCount", 0),
            reverse=True,
        )
        courses = sorted(
            node.get("courseCodes", []),
            key=lambda c: c.get("courseCount", 0),
            reverse=True,
        )

        reviews = []
        for edge in node.get("ratings", {}).get("edges", []):
            r = edge["node"]
            reviews.append(
                {
                    "class": r.get("class"),
                    "date": (r.get("date") or "")[:10],
                    "quality": r.get("helpfulRating"),
                    "clarity": r.get("clarityRating"),
                    "difficulty": r.get("difficultyRating"),
                    "comment": (r.get("comment") or "")[:300],
                    "grade": r.get("grade"),
                    "would_take_again": r.get("wouldTakeAgain"),
                    "online": r.get("isForOnlineClass"),
                    "tags": r.get("ratingTags", ""),
                }
            )

        prof = ProfessorProfile(
            rmp_id=node["id"],
            first_name=node["firstName"],
            last_name=node["lastName"],
            department=node.get("department", "Unknown"),
            avg_rating=node.get("avgRating"),
            avg_difficulty=node.get("avgDifficulty"),
            would_take_again=node.get("wouldTakeAgainPercent"),
            num_ratings=node.get("numRatings", 0),
            tags=[(t["tagName"], t["tagCount"]) for t in tags],
            courses=[(c["courseName"], c["courseCount"]) for c in courses],
            reviews=reviews,
        )

        self._cache.set(cache_key, prof)
        return prof
