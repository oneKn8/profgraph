"""Unit tests for TTLCache (no network required)."""

import time

from profgraph.cache import TTLCache


class TestTTLCache:
    def test_set_and_get(self):
        c = TTLCache()
        c.set("key", "value")
        assert c.get("key") == "value"

    def test_missing_key(self):
        c = TTLCache()
        assert c.get("missing") is None

    def test_expiry(self):
        c = TTLCache(default_ttl=0)
        c.set("key", "value")
        time.sleep(0.01)
        assert c.get("key") is None

    def test_custom_ttl(self):
        c = TTLCache(default_ttl=3600)
        c.set("key", "value", ttl=0)
        time.sleep(0.01)
        assert c.get("key") is None

    def test_clear(self):
        c = TTLCache()
        c.set("a", 1)
        c.set("b", 2)
        c.clear()
        assert c.get("a") is None
        assert c.get("b") is None

    def test_overwrite(self):
        c = TTLCache()
        c.set("key", "old")
        c.set("key", "new")
        assert c.get("key") == "new"

    def test_concurrent_expiry_safe(self):
        """pop(key, None) should not raise even if key was already removed."""
        c = TTLCache(default_ttl=0)
        c.set("key", "value")
        time.sleep(0.01)
        # First get triggers pop
        assert c.get("key") is None
        # Second get should also be safe (key already gone)
        assert c.get("key") is None
