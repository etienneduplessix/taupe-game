import asyncio
import json
import random
import uuid
from datetime import datetime
from typing import Optional, Dict, Set

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

from config import settings
from database import get_db
from models import Session, Round, User, Attempt
from websocket_manager import ws_manager
from score_manager import ScoreManager

DEFAULT_CONFIG = {
    "base_spawn_interval_ms": 1500,
    "base_timeout_ms": 1200,
    "allowed_keys": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
    "scaling_exponent": 1,
    "min_spawn_interval_ms": 300,
    "min_timeout_ms": 250,
    "miss_penalty": -5,
    "max_mistakes": 5,
    "speed_window_size": 10,
    "max_avg_latency_ms": 800,
    "timeouts_count_as_mistakes": True
}

class GameLoop:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_running = False
        self.current_round = 0
        self.alive_players: Set[str] = set()
        self.initial_player_count = 0
        self.config: dict = dict(DEFAULT_CONFIG)
        self.task: Optional[asyncio.Task] = None
        self.score_manager: Optional[ScoreManager] = None
        # Current round state (set inside _run_loop)
        self.current_round_id: Optional[str] = None
        self.current_target_key: Optional[str] = None
        self.current_spawn_ts: Optional[datetime] = None
        self.current_timeout_ms: int = 0
        self.round_attempts: Set[str] = set()

    async def load_config(self, db: AsyncSession):
        result = await db.execute(select(Session).where(Session.id == self.session_id))
        session = result.scalars().first()
        if session:
            self.config = session.config_json
        else:
            self.config = dict(DEFAULT_CONFIG)

    async def start(self, db_factory):
        self.is_running = True
        # Map active connections to alive players
        self.alive_players = set(ws_manager.active_connections.keys())

        # Initialize score manager
        self.score_manager = ScoreManager(self.session_id, self.alive_players, self.config)

        # Announce initial alive count
        await self._broadcast_alive_count()

        self.task = asyncio.create_task(self._run_loop(db_factory))

    async def stop(self):
        self.is_running = False
        if self.task:
            self.task.cancel()

    async def _broadcast_alive_count(self):
        await ws_manager.broadcast({
            "type": "alive_count",
            "data": {
                "session_id": self.session_id,
                "count": len(self.alive_players),
            }
        })

    async def _run_loop(self, db_factory):
        # Store initial count for scaling
        self.initial_player_count = len(self.alive_players)
        print(f"🎮 Game loop starting, initial players: {self.initial_player_count}")

        try:
            while self.is_running:
                if len(self.alive_players) <= 1 and self.initial_player_count > 1:
                    print("🏁 Game over — only one player alive")
                    await ws_manager.broadcast({
                        "type": "game_over",
                        "data": {
                            "session_id": self.session_id,
                            "winner_id": next(iter(self.alive_players)) if self.alive_players else None,
                        }
                    })
                    self.is_running = False
                    break

                self.current_round += 1
                print(f"🔁 Round {self.current_round} starting")

                # 1. Calculate dynamic scaling
                alive_count = len(self.alive_players)
                factor = alive_count / self.initial_player_count if self.initial_player_count > 0 else 1.0
                k = self.config.get("scaling_exponent", 1)
                scaling_val = factor ** k

                base_spawn = self.config.get("base_spawn_interval_ms", 1500)
                min_spawn = self.config.get("min_spawn_interval_ms", 300)
                interval_ms = int(min_spawn + (base_spawn - min_spawn) * scaling_val)

                base_timeout = self.config.get("base_timeout_ms", 1200)
                min_timeout = self.config.get("min_timeout_ms", 250)
                timeout_ms = int(min_timeout + (base_timeout - min_timeout) * scaling_val)

                # 2. Pick a target key (normalized to keyboard-compatible uppercase keys)
                raw_keys = self.config.get("allowed_keys", DEFAULT_CONFIG["allowed_keys"])
                if not isinstance(raw_keys, str):
                    raw_keys = str(raw_keys or "")
                keys = [k for k in raw_keys.upper() if k.isalnum()]
                if not keys:
                    keys = list(DEFAULT_CONFIG["allowed_keys"])
                target_key = random.choice(keys)
                print(f"🎯 Picked key: {target_key}")

                # 3. Record round in DB (optional - skip if fails)
                spawn_ts = datetime.utcnow()
                round_id = str(uuid.uuid4())

                # Stash current-round state for process_attempt / timeout resolver
                self.current_round_id = round_id
                self.current_target_key = target_key
                self.current_spawn_ts = spawn_ts
                self.current_timeout_ms = timeout_ms
                self.round_attempts = set()

                try:
                    async with db_factory() as db:
                        new_round = Round(
                            id=round_id,
                            session_id=self.session_id,
                            round_number=self.current_round,
                            target_key=target_key,
                            spawn_ts=spawn_ts,
                            timeout_ms=timeout_ms,
                            interval_ms=interval_ms
                        )
                        db.add(new_round)
                        await db.commit()
                except Exception as e:
                    print(f"⚠️  DB error (non-fatal): {e}")

                # 4. Broadcast taupe spawn
                await ws_manager.broadcast({
                    "type": "taupe_spawn",
                    "data": {
                        "session_id": self.session_id,
                        "round_id": round_id,
                        "key": target_key,
                        "timeout_ms": timeout_ms
                    }
                })

                # 5. Wait the response window, then resolve timeouts
                await asyncio.sleep(timeout_ms / 1000.0)
                await self._resolve_round_timeouts()

                # 6. Flush attempts to DB every round
                if self.score_manager:
                    try:
                        async with db_factory() as db:
                            await self.score_manager.flush_attempts(db)
                    except Exception as e:
                        print(f"⚠️  Flush error (non-fatal): {e}")

                # 7. Inter-round gap so total cycle stays ~interval_ms
                remaining = max(0.0, (interval_ms - timeout_ms) / 1000.0)
                if remaining > 0:
                    await asyncio.sleep(remaining)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"❌ Game loop crashed: {e}")
            import traceback
            traceback.print_exc()

    async def _resolve_round_timeouts(self):
        """For each alive player who didn't attempt this round, record a timeout."""
        if not self.score_manager or not self.current_round_id:
            return
        for user_id in list(self.alive_players):
            if user_id in self.round_attempts:
                continue
            self.score_manager.update_score(
                user_id,
                self.current_round_id,
                self.current_timeout_ms,
                "timeout",
                self.current_round,
            )
            # Persist the synthetic timeout attempt
            self.score_manager.add_attempt(Attempt(
                round_id=self.current_round_id,
                user_id=user_id,
                pressed_key=None,
                latency_ms=self.current_timeout_ms,
                outcome="timeout",
            ))
            await self._maybe_eliminate(user_id)

    async def _maybe_eliminate(self, user_id: str):
        if not self.score_manager:
            return
        eliminated, reason = self.score_manager.check_elimination(user_id, self.current_round)
        if not eliminated:
            return
        self.alive_players.discard(user_id)
        self.score_manager.eliminate_player(user_id, reason, self.current_round)
        await ws_manager.send_personal_message({
            "type": "player_eliminated",
            "data": {
                "session_id": self.session_id,
                "reason": reason,
                "round": self.current_round,
            }
        }, user_id)
        await self._broadcast_alive_count()

    async def process_attempt(self, user_id: str, attempt_data: dict):
        if not self.is_running or user_id not in self.alive_players or not self.score_manager:
            return
        if not self.current_round_id:
            return

        round_id = attempt_data.get("round_id")
        if round_id != self.current_round_id:
            return  # stale or unknown round
        if user_id in self.round_attempts:
            return  # one shot per round

        pressed_key = (attempt_data.get("key") or "").upper()
        latency_ms = max(0, int((datetime.utcnow() - self.current_spawn_ts).total_seconds() * 1000)) if self.current_spawn_ts else 0
        outcome = "hit" if pressed_key == self.current_target_key else "miss"

        self.round_attempts.add(user_id)

        # Persist the attempt for later flush
        self.score_manager.add_attempt(Attempt(
            round_id=round_id,
            user_id=user_id,
            pressed_key=pressed_key[:1] if pressed_key else None,
            latency_ms=latency_ms,
            outcome=outcome,
        ))

        self.score_manager.update_score(user_id, round_id, latency_ms, outcome, self.current_round)
        await self._maybe_eliminate(user_id)

# Global registry to manage active game loops
active_games: Dict[str, GameLoop] = {}

async def start_game(session_id: str, db_factory):
    if session_id not in active_games:
        game = GameLoop(session_id)
        active_games[session_id] = game

    await active_games[session_id].start(db_factory)
