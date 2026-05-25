"""Smoke test: both game types are registered and instantiable.

Run from the backend dir:
    python -m pytest tests/test_game_registry.py -q
or:
    python -m tests.test_game_registry
"""
import os
import sys
import unittest

# Allow running this file standalone via `python tests/test_game_registry.py`
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Settings module reads env at import time, so seed minimal values.
os.environ.setdefault("FT_CLIENT_ID", "x")
os.environ.setdefault("FT_CLIENT_SECRET", "x")
os.environ.setdefault("FT_REDIRECT_URI", "http://localhost/cb")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ADMIN_LOGINS", "")
os.environ.setdefault("POSTGRES_USER", "u")
os.environ.setdefault("POSTGRES_PASSWORD", "p")
os.environ.setdefault("POSTGRES_DB", "x")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/x")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


class GameRegistryTest(unittest.TestCase):
    def test_both_game_types_registered(self):
        from game_loop import GAME_LOOPS, GAME_TYPE_TAUPE, GAME_TYPE_DOT_RUSH, BaseGameLoop

        self.assertIn(GAME_TYPE_TAUPE, GAME_LOOPS)
        self.assertIn(GAME_TYPE_DOT_RUSH, GAME_LOOPS)

        for game_type, cls in GAME_LOOPS.items():
            self.assertTrue(issubclass(cls, BaseGameLoop), f"{game_type} is not a BaseGameLoop subclass")
            instance = cls(session_id=f"test-{game_type}")
            self.assertEqual(instance.session_id, f"test-{game_type}")
            self.assertEqual(instance.game_type, game_type)
            self.assertFalse(instance.is_running)
            self.assertEqual(instance.alive_players, set())

    def test_resolve_by_game_type(self):
        from game_loop import _resolve_game_class, TaupeGameLoop
        from games.dot_rush import DotRushGameLoop

        self.assertIs(_resolve_game_class({"game_type": "taupe"}), TaupeGameLoop)
        self.assertIs(_resolve_game_class({"game_type": "dot_rush"}), DotRushGameLoop)
        self.assertIs(_resolve_game_class({}), TaupeGameLoop)
        self.assertIs(_resolve_game_class(None), TaupeGameLoop)
        # Unknown types fall back to taupe (back-compat)
        self.assertIs(_resolve_game_class({"game_type": "nonexistent"}), TaupeGameLoop)


if __name__ == "__main__":
    unittest.main()
