import asyncio
from typing import Dict, List, Set
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from models import Attempt, SessionScore, Round

class ScoreManager:
    def __init__(self, session_id: str, initial_players: Set[str], config: dict):
        self.session_id = session_id
        self.config = config
        self.scores: Dict[str, Dict] = {
            user_id: {
                "score": 0,
                "hits": 0,
                "misses": 0,
                "timeouts": 0,
                "latencies": [],
                "consecutive_hits": 0,
                "total_mistakes": 0,
                "eliminated": False,
                "reason": None,
                "elimination_round": None
            } for user_id in initial_players
        }
        self.pending_attempts: List[Attempt] = []

    def update_score(self, user_id: str, round_id: str, latency_ms: int, outcome: str, round_number: int):
        if user_id not in self.scores or self.scores[user_id]["eliminated"]:
            return

        s = self.scores[user_id]
        
        if outcome == "hit":
            # Points = max(1, 100 - latency_ms / 10)
            points = max(1, int(100 - latency_ms / 10))
            
            # Combo Multipliers
            multiplier = 1.0
            if s["consecutive_hits"] >= 20: multiplier = 3.0
            elif s["consecutive_hits"] >= 10: multiplier = 2.0
            elif s["consecutive_hits"] >= 5: multiplier = 1.5
            
            s["score"] += int(points * multiplier)
            s["hits"] += 1
            s["consecutive_hits"] += 1
            s["latencies"].append(latency_ms)
        elif outcome == "miss":
            s["score"] += self.config.get("miss_penalty", -5)
            s["misses"] += 1
            s["consecutive_hits"] = 0
            s["total_mistakes"] += 1
        elif outcome == "timeout":
            s["timeouts"] += 1
            s["consecutive_hits"] = 0
            if self.config.get("timeouts_count_as_mistakes", True):
                s["total_mistakes"] += 1

    def check_elimination(self, user_id: str, round_number: int) -> tuple[bool, str]:
        s = self.scores[user_id]
        
        # Mistake Elimination
        max_mistakes = self.config.get("max_mistakes", 5)
        if s["total_mistakes"] >= max_mistakes:
            return True, "mistakes"

        # Speed Elimination
        window_size = self.config.get("speed_window_size", 10)
        max_avg_latency = self.config.get("max_avg_latency_ms", 800)
        
        if len(s["latencies"]) >= window_size:
            recent_latencies = s["latencies"][-window_size:]
            avg_latency = sum(recent_latencies) / window_size
            if avg_latency > max_avg_latency:
                return True, "speed"

        return False, ""

    def eliminate_player(self, user_id: str, reason: str, round_number: int):
        if user_id in self.scores:
            self.scores[user_id]["eliminated"] = True
            self.scores[user_id]["reason"] = reason
            self.scores[user_id]["elimination_round"] = round_number

    async def flush_attempts(self, db: AsyncSession):
        if not self.pending_attempts:
            return
        
        db.add_all(self.pending_attempts)
        await db.commit()
        self.pending_attempts = []

    def add_attempt(self, attempt: Attempt):
        self.pending_attempts.append(attempt)
