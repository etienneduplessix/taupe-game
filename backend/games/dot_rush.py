"""Dot Rush — a mouse-based reaction game.

Each round, the server picks a random (x%, y%) on a 0–100 normalized canvas
and a radius/lifetime. The first player to click inside the dot scores and
ends the round. Anyone who didn't click in time gets a miss; max_misses
misses → elimination. Last player standing wins.

This intentionally exercises a different shape than the taupe game:
- Mouse input instead of keyboard
- "Race to claim" round resolution instead of per-player attempts
- No DB per-round record (Round table is taupe-shaped); v1 lives in memory.
"""

import asyncio
import math
import random
import uuid
from datetime import datetime
from typing import Optional, Set

from websocket_manager import ws_manager
from game_loop import BaseGameLoop, GAME_TYPE_DOT_RUSH


DOT_RUSH_DEFAULTS = {
    "max_misses": 3,
    "initial_lifetime_ms": 1500,
    "min_lifetime_ms": 400,
    "initial_radius_pct": 8.0,
    "min_radius_pct": 2.5,
    "inter_round_gap_ms": 600,
    "scaling_exponent": 1.0,
    "countdown_seconds": 5,
}


class DotRushGameLoop(BaseGameLoop):
    game_type = GAME_TYPE_DOT_RUSH

    def __init__(self, session_id: str):
        super().__init__(session_id)
        # current round state
        self.current_round_id: Optional[str] = None
        self.current_x: float = 0.0
        self.current_y: float = 0.0
        self.current_radius: float = 0.0
        self.current_lifetime_ms: int = 0
        self.current_spawn_ts: Optional[datetime] = None
        self.round_claimed_by: Optional[str] = None
        self.round_event: Optional[asyncio.Event] = None
        # per-player misses
        self.misses: dict[str, int] = {}

    def _cfg(self, key: str):
        return self.config.get(key, DOT_RUSH_DEFAULTS[key])

    def _ensure_player(self, user_id: str):
        self.misses.setdefault(user_id, 0)

    async def add_player(self, user_id: str):
        await super().add_player(user_id)
        self._ensure_player(user_id)

    async def _run_rounds(self, db_factory):
        max_misses = int(self._cfg("max_misses"))
        initial_lifetime = float(self._cfg("initial_lifetime_ms"))
        min_lifetime = float(self._cfg("min_lifetime_ms"))
        initial_radius = float(self._cfg("initial_radius_pct"))
        min_radius = float(self._cfg("min_radius_pct"))
        gap_ms = int(self._cfg("inter_round_gap_ms"))
        k = float(self._cfg("scaling_exponent"))

        while self.is_running:
            if not self.alive_players:
                await asyncio.sleep(0.5)
                continue

            if await self._check_game_over():
                break

            self.current_round += 1

            alive = len(self.alive_players)
            factor = alive / self.initial_player_count if self.initial_player_count > 0 else 1.0
            scaling = factor ** k

            lifetime_ms = int(min_lifetime + (initial_lifetime - min_lifetime) * scaling)
            radius_pct = min_radius + (initial_radius - min_radius) * scaling

            # Keep the dot fully inside the canvas
            margin = radius_pct
            x = random.uniform(margin, 100.0 - margin)
            y = random.uniform(margin, 100.0 - margin)

            round_id = str(uuid.uuid4())
            self.current_round_id = round_id
            self.current_x = x
            self.current_y = y
            self.current_radius = radius_pct
            self.current_lifetime_ms = lifetime_ms
            self.current_spawn_ts = datetime.utcnow()
            self.round_claimed_by = None
            self.round_event = asyncio.Event()

            for uid in self.alive_players:
                self._ensure_player(uid)

            await ws_manager.broadcast({
                "type": "dot_spawn",
                "data": {
                    "session_id": self.session_id,
                    "round_id": round_id,
                    "x": x,
                    "y": y,
                    "radius_pct": radius_pct,
                    "lifetime_ms": lifetime_ms,
                    "round_number": self.current_round,
                },
            })

            # Wait for either a successful claim or the lifetime to expire
            try:
                await asyncio.wait_for(self.round_event.wait(), timeout=lifetime_ms / 1000.0)
            except asyncio.TimeoutError:
                pass

            winner = self.round_claimed_by
            if winner:
                await ws_manager.broadcast({
                    "type": "dot_resolved",
                    "data": {
                        "session_id": self.session_id,
                        "round_id": round_id,
                        "winner_id": winner,
                        "expired": False,
                    },
                })
            else:
                # Nobody claimed → everyone alive eats a miss
                eliminated_this_round = []
                for uid in list(self.alive_players):
                    self.misses[uid] = self.misses.get(uid, 0) + 1
                    if self.misses[uid] >= max_misses:
                        eliminated_this_round.append(uid)
                await ws_manager.broadcast({
                    "type": "dot_resolved",
                    "data": {
                        "session_id": self.session_id,
                        "round_id": round_id,
                        "winner_id": None,
                        "expired": True,
                    },
                })
                for uid in eliminated_this_round:
                    await self._eliminate(uid, "mistakes")

            # Reset current round so stale clicks don't register
            self.current_round_id = None
            self.round_event = None

            if gap_ms > 0:
                await asyncio.sleep(gap_ms / 1000.0)

    async def _eliminate(self, user_id: str, reason: str):
        if user_id not in self.alive_players:
            return
        self.alive_players.discard(user_id)
        if self.score_manager:
            self.score_manager.eliminate_player(user_id, reason, self.current_round)
        await ws_manager.send_personal_message({
            "type": "player_eliminated",
            "data": {
                "session_id": self.session_id,
                "reason": reason,
                "round": self.current_round,
            },
        }, user_id)
        await self._broadcast_alive_count()

    async def handle_player_input(self, msg_type: str, user_id: str, payload: dict):
        if msg_type != "dot_click":
            return
        if not self.is_running or user_id not in self.alive_players:
            return
        if not self.current_round_id or self.round_claimed_by is not None:
            return
        if payload.get("round_id") != self.current_round_id:
            return

        try:
            x = float(payload.get("x"))
            y = float(payload.get("y"))
        except (TypeError, ValueError):
            return

        # Hit test inside the dot (in normalized percentage space)
        dx = x - self.current_x
        dy = y - self.current_y
        inside = math.hypot(dx, dy) <= self.current_radius

        if inside:
            self.round_claimed_by = user_id
            latency_ms = max(0, int((datetime.utcnow() - self.current_spawn_ts).total_seconds() * 1000)) if self.current_spawn_ts else 0
            if self.score_manager and user_id in self.score_manager.scores:
                # Score: reward speed, mirror taupe's max(1, 100 - latency/10)
                s = self.score_manager.scores[user_id]
                points = max(1, int(100 - latency_ms / 10))
                s["score"] += points
                s["hits"] += 1
                s["latencies"].append(latency_ms)
            if self.round_event:
                self.round_event.set()
        else:
            # Wrong click counts as a miss for this player
            max_misses = int(self._cfg("max_misses"))
            self.misses[user_id] = self.misses.get(user_id, 0) + 1
            if self.score_manager and user_id in self.score_manager.scores:
                s = self.score_manager.scores[user_id]
                s["misses"] += 1
                s["score"] += int(self.config.get("miss_penalty", -5))
            await ws_manager.send_personal_message({
                "type": "dot_miss",
                "data": {
                    "session_id": self.session_id,
                    "round_id": self.current_round_id,
                    "misses": self.misses[user_id],
                    "max_misses": max_misses,
                },
            }, user_id)
            if self.misses[user_id] >= max_misses:
                await self._eliminate(user_id, "mistakes")
