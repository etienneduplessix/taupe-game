"""Among Us — 2D social deduction game.

Crewmates complete tasks on a shared tile map. Impostors secretly kill
crewmates. Bodies can be reported to trigger discussion and voting.

Architecture:
- Movement at ~16Hz: clients send `among_us_move`, server broadcasts
  aggregated state snapshots to all players.
- Game logic (kills, tasks, meetings, voting) is server-authoritative
  and runs inside the game loop tick.
- Redis pub/sub is used for fan-out broadcast (via ws_manager.broadcast).
"""

import asyncio
import math
import random
from typing import Optional

from websocket_manager import ws_manager
from game_loop import BaseGameLoop

GAME_TYPE_AMONG_US = "among_us"

# Campus map (42 Prague). Cells: W=wall, .=floor, 1-8=task zones (-> T1..T8).
# Layout aligns with frontend/public/maps/campus.svg (building interior).
SHIP_MAP = [
    "WWWWWWWWWWWWWWWWWWWWWW",
    "W....................W",
    "W........1...........W",
    "W....................W",
    "W....................W",
    "W....................W",
    "W.3..................W",
    "W.......WWWWW........W",
    "W.......WWWWW........W",
    "W.......WWWWW........W",
    "W....................W",
    "W.................2..W",
    "W....................W",
    "W....................W",
    "W.......WWWWW........W",
    "W.......WWWWW........W",
    "W.......WWWWW........W",
    "W....................W",
    "W....................W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W..4...WWWWWWW...6...W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W.5....WWWWWWW.......W",
    "W......WWWWWWW.......W",
    "W..................7.W",
    "W....................W",
    "W....................W",
    "W....................W",
    "W.........8..........W",
    "WWWWWWWWWWWWWWWWWWWWWW",
]

TASK_ZONES = {
    "T1": {"type": "button_press", "label": "Cluster 1",  "duration": 3.0},
    "T2": {"type": "wire_connect", "label": "Cluster 1",  "sequence": ["A", "B", "C", "D"]},
    "T3": {"type": "swipe_card",   "label": "Cluster 3",  "duration": 4.0},
    "T4": {"type": "upload_data",  "label": "Kitchen",    "duration": 5.0},
    "T5": {"type": "calibrate",    "label": "Cluster 2",  "clicks": 3},
    "T6": {"type": "button_press", "label": "Auditorium", "duration": 3.0},
    "T7": {"type": "wire_connect", "label": "Server Room", "sequence": ["1", "2", "3", "4"]},
    "T8": {"type": "swipe_card",   "label": "Cluster 2",  "duration": 4.0},
}

AMONG_US_DEFAULTS = {
    "game_type": "among_us",
    "min_players": 4,
    "max_players": 10,
    "impostor_count": 1,
    "kill_cooldown_seconds": 25,
    "kill_range": 1.5,
    "report_range": 1.0,
    "discussion_duration_seconds": 30,
    "voting_duration_seconds": 15,
    "tasks_per_crewmate": 4,
    "task_interact_range": 1.35,
    "movement_speed": 4.0,
    "crewmate_vision_radius": 5,
    "impostor_vision_radius": 6,
    "ghost_vision_radius": 8,
    "countdown_seconds": 5,
    "tick_rate_hz": 20,
    "state_broadcast_interval_ticks": 2,
}

PLAYER_COLORS = [
    "#ef4444", "#f97316", "#eab308", "#22c55e",
    "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899",
    "#78716c", "#84cc16",
]


def _parse_map(map_rows):
    walls = set()
    task_zones = {}
    floor = set()
    for row_idx, row in enumerate(map_rows):
        for col_idx, ch in enumerate(row):
            if ch == "W":
                walls.add((col_idx, row_idx))
            elif ch.isdigit():
                task_zones.setdefault("T" + ch, []).append((col_idx, row_idx))
                floor.add((col_idx, row_idx))
            else:
                floor.add((col_idx, row_idx))
    return walls, floor, task_zones


def _distance(a, b):
    return math.hypot(a["x"] - b["x"], a["y"] - b["y"])


class AmongUsGameLoop(BaseGameLoop):
    game_type = GAME_TYPE_AMONG_US

    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.positions: dict[str, dict] = {}
        self.roles: dict[str, str] = {}
        self.is_alive: dict[str, bool] = {}
        self.colors: dict[str, str] = {}
        self.display_names: dict[str, str] = {}

        self.phase: str = "countdown"
        self._frame = 0
        self._tick = 1.0 / self._cfg_int("tick_rate_hz")

        self._kill_cooldowns: dict[str, float] = {}
        self._dead_bodies: list[dict] = []
        self._input_queue: asyncio.Queue = asyncio.Queue()

        self._task_list: list[str] = list(TASK_ZONES.keys())
        self.tasks_assigned: dict[str, list[str]] = {}
        self.tasks_completed: dict[str, list[str]] = {}
        self._task_timers: dict[str, dict] = {}
        self._task_progress: dict[str, float] = {}
        self._task_total: int = 0
        self._task_done: int = 0

        self._meeting: Optional[dict] = None
        self._votes: dict[str, str] = {}

        self._walls, self._floor, self._map_task_zones = _parse_map(SHIP_MAP)
        self.map_width = len(SHIP_MAP[0])
        self.map_height = len(SHIP_MAP)
        self._map_spawns = [(16, 5), (4, 5), (17, 33), (4, 33), (10, 32), (15, 18), (5, 18), (10, 5)]

        self._sabotage_timers: dict[str, float] = {}
        self._lights_out: bool = False

    # ------------------------------------------------------------------ helpers

    def _cfg(self, key, default=None):
        return self.config.get(key, AMONG_US_DEFAULTS.get(key, default))

    def _cfg_int(self, key):
        return int(self._cfg(key))

    def _cfg_float(self, key):
        return float(self._cfg(key))

    # ------------------------------------------------------------------ player management

    def _assign_roles(self):
        players = list(self.alive_players)
        if not players:
            return
        impostor_count = min(
            self._cfg_int("impostor_count"),
            max(1, len(players) // 4),
        )
        impostors = set(random.sample(players, impostor_count))
        for pid in players:
            role = "impostor" if pid in impostors else "crewmate"
            self.roles[pid] = role
            self.is_alive[pid] = True
            self._kill_cooldowns[pid] = 0.0

        for pid in impostors:
            self.colors.setdefault(pid, "#ef4444")

    def _assign_tasks(self):
        self.tasks_assigned.clear()
        self.tasks_completed.clear()
        self._task_done = 0
        self._task_total = 0
        per_person = max(1, self._cfg_int("tasks_per_crewmate"))
        crewmates = [pid for pid, r in self.roles.items() if r == "crewmate"]
        for pid in crewmates:
            assigned = random.sample(self._task_list, k=min(per_person, len(self._task_list)))
            self.tasks_assigned[pid] = assigned
            self.tasks_completed[pid] = []
            self._task_total += len(assigned)

    def _assign_tasks_to_player(self, user_id: str):
        if self.roles.get(user_id) != "crewmate":
            return
        if user_id in self.tasks_assigned:
            return
        per_person = max(1, self._cfg_int("tasks_per_crewmate"))
        assigned = random.sample(self._task_list, k=min(per_person, len(self._task_list)))
        self.tasks_assigned[user_id] = assigned
        self.tasks_completed[user_id] = []
        self._task_total += len(assigned)

    async def add_player(self, user_id: str):
        await super().add_player(user_id)
        if user_id not in self.positions:
            spawn = self._map_spawns[len(self.positions) % len(self._map_spawns)]
            self.positions[user_id] = {"x": float(spawn[0]) + 0.5, "y": float(spawn[1]) + 0.5}
        idx = len(self.alive_players) - 1
        self.colors.setdefault(user_id, PLAYER_COLORS[idx % len(PLAYER_COLORS)])
        self.display_names[user_id] = user_id
        if user_id not in self.roles:
            self.roles[user_id] = "crewmate"
            self.is_alive[user_id] = True
            self._kill_cooldowns[user_id] = 0.0
        self._assign_tasks_to_player(user_id)
        if self.phase in ("playing", "meeting"):
            await ws_manager.send_personal_message({
                "type": "among_us_role",
                "data": {
                    "session_id": self.session_id,
                    "role": self.roles.get(user_id, "crewmate"),
                    "tasks": self.tasks_assigned.get(user_id, []),
                },
            }, user_id)
            await self._broadcast_alive_count()
            await self._broadcast_state()

    def set_player_display_name(self, user_id: str, display_name: str):
        if display_name:
            self.display_names[user_id] = display_name

    async def remove_player(self, user_id: str):
        # A browser refresh briefly closes the WebSocket. Keep Among Us players
        # in the match so they can reconnect without being eliminated.
        await self._broadcast_alive_count()

    # ------------------------------------------------------------------ collision

    def _collides_wall(self, x: float, y: float) -> bool:
        margin = 0.2
        corners = [
            (x + margin, y + margin),
            (x - margin, y + margin),
            (x + margin, y - margin),
            (x - margin, y - margin),
        ]
        for cx, cy in corners:
            tile_x, tile_y = int(cx), int(cy)
            if (tile_x, tile_y) in self._walls:
                return True
            if not (0 <= tile_x < self.map_width and 0 <= tile_y < self.map_height):
                return True
        return False

    def _tile_at(self, x: float, y: float) -> tuple:
        return (int(x), int(y))

    # ------------------------------------------------------------------ game phases

    def _state_payload_for(self, viewer_id: str):
        players = []
        viewer_role = self.roles.get(viewer_id, "crewmate")
        for pid in self.positions:
            if pid not in self.alive_players:
                continue
            p = self.positions[pid]
            role = self.roles.get(pid, "crewmate")
            visible_role = role if pid == viewer_id or (viewer_role == "impostor" and role == "impostor") else "unknown"
            vision = (
                self._cfg_float("impostor_vision_radius")
                if role == "impostor" and self.is_alive.get(pid)
                else self._cfg_float("crewmate_vision_radius")
            )
            if not self.is_alive.get(pid):
                vision = self._cfg_float("ghost_vision_radius")
            players.append({
                "id": pid,
                "x": p["x"],
                "y": p["y"],
                "alive": self.is_alive.get(pid, False),
                "role": visible_role,
                "color": self.colors.get(pid, "#888"),
                "display_name": self.display_names.get(pid, pid),
                "vision_radius": vision,
            })

        return {
            "type": "among_us_state",
            "data": {
                "session_id": self.session_id,
                "phase": self.phase,
                "players": players,
                "task_progress": {
                    "done": self._task_done,
                    "total": self._task_total,
                },
                "dead_bodies": self._dead_bodies,
                "lights_out": self._lights_out,
            },
        }

    async def _broadcast_state(self):
        for viewer_id in list(self.alive_players):
            await ws_manager.send_personal_message(self._state_payload_for(viewer_id), viewer_id)

    def _update_cooldowns(self, dt: float):
        for pid in list(self._kill_cooldowns):
            if self._kill_cooldowns[pid] > 0:
                self._kill_cooldowns[pid] = max(0, self._kill_cooldowns[pid] - dt)

        for key in list(self._sabotage_timers):
            if self._sabotage_timers[key] > 0:
                self._sabotage_timers[key] = max(0, self._sabotage_timers[key] - dt)
            if key == "lights" and self._sabotage_timers.get("lights", 0) <= 0:
                self._lights_out = False

    async def _process_queued_inputs(self):
        while not self._input_queue.empty():
            try:
                msg_type, user_id, payload = self._input_queue.get_nowait()
                await self._handle_input(msg_type, user_id, payload)
            except asyncio.QueueEmpty:
                break

    async def _handle_input(self, msg_type: str, user_id: str, payload: dict):
        if msg_type == "among_us_move":
            self._handle_move(user_id, payload)
        elif msg_type == "among_us_kill":
            self._handle_kill(user_id, payload)
        elif msg_type == "among_us_report":
            self._handle_report(user_id)
        elif msg_type == "among_us_vote":
            self._handle_vote(user_id, payload)
        elif msg_type == "among_us_task_start":
            self._handle_task_start(user_id, payload)
        elif msg_type == "among_us_task_step":
            self._handle_task_step(user_id, payload)
        elif msg_type == "among_us_sabotage":
            self._handle_sabotage(user_id, payload)

    # ------------------------------------------------------------------ movement

    def _handle_move(self, user_id: str, payload: dict):
        if self.phase != "playing":
            return
        if user_id not in self.alive_players:
            return

        x = float(payload.get("x") or 0)
        y = float(payload.get("y") or 0)
        if not (0 <= x < self.map_width and 0 <= y < self.map_height):
            return
        if self._collides_wall(x, y):
            return
        self.positions[user_id] = {"x": x, "y": y}

    # ------------------------------------------------------------------ kill

    def _handle_kill(self, user_id: str, payload: dict):
        if self.phase != "playing":
            return
        if self.roles.get(user_id) != "impostor":
            return
        if not self.is_alive.get(user_id):
            return
        if self._kill_cooldowns.get(user_id, 0) > 0:
            return

        target_id = payload.get("target_id")
        if not target_id:
            return
        if target_id not in self.alive_players:
            return
        if self.roles.get(target_id) != "crewmate":
            return
        if not self.is_alive.get(target_id, False):
            return

        killer_pos = self.positions.get(user_id)
        victim_pos = self.positions.get(target_id)
        if not killer_pos or not victim_pos:
            return

        kill_range = self._cfg_float("kill_range")
        if _distance(killer_pos, victim_pos) > kill_range:
            return

        self.is_alive[target_id] = False
        self._kill_cooldowns[user_id] = self._cfg_float("kill_cooldown_seconds")

        body = {
            "x": victim_pos["x"],
            "y": victim_pos["y"],
            "victim_id": target_id,
            "color": self.colors.get(target_id, "#888"),
        }
        self._dead_bodies.append(body)

        asyncio.create_task(self._broadcast_event("kill", {
            "killer_id": user_id,
            "victim_id": target_id,
            "body": body,
        }))

        asyncio.create_task(self._check_win_async())

    # ------------------------------------------------------------------ report

    def _handle_report(self, user_id: str):
        if self.phase != "playing":
            return
        if user_id not in self.alive_players:
            return
        if not self.is_alive.get(user_id):
            return
        if not self._dead_bodies:
            return

        player_pos = self.positions.get(user_id)
        if not player_pos:
            return

        report_range = self._cfg_float("report_range")
        reported = None
        for body in self._dead_bodies:
            if _distance(player_pos, body) < report_range:
                reported = body
                break
        if not reported:
            return

        self._dead_bodies.clear()
        self._start_meeting(user_id, reported["victim_id"])

    # ------------------------------------------------------------------ tasks

    def _handle_task_start(self, user_id: str, payload: dict):
        if self.phase != "playing":
            return
        if self.roles.get(user_id) != "crewmate":
            return
        if not self.is_alive.get(user_id):
            return

        task_id = payload.get("task_id")
        if not task_id or task_id not in self.tasks_assigned.get(user_id, []):
            return
        if task_id in self.tasks_completed.get(user_id, []):
            return

        player_pos = self.positions.get(user_id)
        if not player_pos:
            return
        task_tiles = self._map_task_zones.get(task_id, [])
        interact_range = self._cfg_float("task_interact_range")
        is_near_task = any(
            math.hypot(player_pos["x"] - (tx + 0.5), player_pos["y"] - (ty + 0.5)) <= interact_range
            for tx, ty in task_tiles
        )
        if not is_near_task:
            return

        task_def = TASK_ZONES.get(task_id)
        if not task_def:
            return

        if task_def["type"] in ("button_press", "swipe_card", "upload_data"):
            self._task_timers[user_id] = {
                "task_id": task_id,
                "remaining": max(task_def["duration"] + 8.0, 10.0),
                "total": task_def["duration"],
            }
        elif task_def["type"] == "calibrate":
            self._task_progress[user_id] = 0.0
            self._task_timers[user_id] = {
                "task_id": task_id,
                "clicks": task_def["clicks"],
                "done": 0,
            }
        elif task_def["type"] == "wire_connect":
            self._task_timers[user_id] = {
                "task_id": task_id,
                "sequence": task_def["sequence"],
                "step": 0,
            }

        asyncio.create_task(self._broadcast_event("task_started", {
            "player_id": user_id,
            "task_id": task_id,
            "task_type": task_def["type"],
        }))

    def _handle_task_step(self, user_id: str, payload: dict):
        timer = self._task_timers.get(user_id)
        if not timer:
            return
        task_id = timer["task_id"]
        task_def = TASK_ZONES.get(task_id)
        if not task_def:
            return

        if task_def["type"] == "calibrate":
            timer["done"] += 1
            self._task_progress[user_id] = timer["done"] / task_def["clicks"]
            if timer["done"] >= task_def["clicks"]:
                self._complete_task(user_id, task_id)
        elif task_def["type"] == "wire_connect":
            step_val = payload.get("step")
            expected = task_def["sequence"][timer["step"]] if timer["step"] < len(task_def["sequence"]) else None
            if step_val == expected:
                timer["step"] += 1
            else:
                timer["step"] = 0
            if timer["step"] >= len(task_def["sequence"]):
                self._complete_task(user_id, task_id)
        elif task_def["type"] in ("button_press", "swipe_card", "upload_data"):
            if payload.get("task_id") == task_id:
                self._complete_task(user_id, task_id)

    def _complete_task(self, user_id: str, task_id: str):
        if task_id in self.tasks_completed.get(user_id, []):
            return
        self.tasks_completed.setdefault(user_id, []).append(task_id)
        self._task_timers.pop(user_id, None)
        self._task_progress.pop(user_id, None)
        self._task_done += 1
        asyncio.create_task(self._broadcast_event("task_complete", {
            "player_id": user_id,
            "task_id": task_id,
            "progress": {"done": self._task_done, "total": self._task_total},
        }))
        asyncio.create_task(self._check_win_async())

    # ------------------------------------------------------------------ meeting

    def _start_meeting(self, reporter_id: str, victim_id: Optional[str] = None):
        self.phase = "meeting"
        self._votes = {}
        discussion = self._cfg_int("discussion_duration_seconds")
        voting = self._cfg_int("voting_duration_seconds")
        alive = [pid for pid, a in self.is_alive.items() if a and pid in self.alive_players]
        self._meeting = {
            "reporter_id": reporter_id,
            "victim_id": victim_id,
            "discussion_remaining": discussion,
            "voting_remaining": voting,
            "participants": alive,
        }
        asyncio.create_task(ws_manager.broadcast({
            "type": "meeting_start",
            "data": {
                "session_id": self.session_id,
                "reporter_id": reporter_id,
                "victim_id": victim_id,
                "discussion_seconds": discussion,
                "voting_seconds": voting,
                "participants": [{
                    "id": pid,
                    "display_name": self.display_names.get(pid, pid),
                    "color": self.colors.get(pid, "#888"),
                } for pid in alive],
            },
        }))

    async def _update_meeting(self, dt: float):
        if not self._meeting:
            return
        if self._meeting["discussion_remaining"] > 0:
            self._meeting["discussion_remaining"] -= dt
            if self._meeting["discussion_remaining"] <= 0:
                self._meeting["discussion_remaining"] = 0
                asyncio.create_task(ws_manager.broadcast({
                    "type": "meeting_vote_phase",
                    "data": {
                        "session_id": self.session_id,
                        "voting_seconds": self._meeting["voting_remaining"],
                    },
                }))
            return

        self._meeting["voting_remaining"] -= dt
        if self._meeting["voting_remaining"] <= 0:
            await self._resolve_meeting()

    async def _resolve_meeting(self):
        if not self._meeting:
            return

        tally: dict[str, int] = {}
        for voter, target in self._votes.items():
            if target != "skip":
                tally[target] = tally.get(target, 0) + 1

        skip_count = sum(1 for t in self._votes.values() if t == "skip")
        ejected = None
        if tally:
            most_votes = max(tally.values())
            if most_votes > skip_count:
                candidates = [pid for pid, c in tally.items() if c == most_votes]
                if len(candidates) == 1:
                    ejected = candidates[0]

        if ejected:
            self.is_alive[ejected] = False
            self.alive_players.discard(ejected)

        await ws_manager.broadcast({
            "type": "meeting_result",
            "data": {
                "session_id": self.session_id,
                "ejected_id": ejected,
                "votes": {v: t for v, t in self._votes.items()},
                "skipped": ejected is None,
            },
        })

        self._meeting = None
        self._votes.clear()
        self._dead_bodies.clear()
        self.phase = "playing"
        await self._broadcast_alive_count()
        asyncio.create_task(self._check_win_async())

    # ------------------------------------------------------------------ votes

    def _handle_vote(self, user_id: str, payload: dict):
        if self.phase != "meeting":
            return
        if not self._meeting:
            return
        if user_id not in self._meeting["participants"]:
            return
        if self._meeting["discussion_remaining"] > 0:
            return
        if user_id in self._votes:
            return
        target = payload.get("target_id", "skip")
        self._votes[user_id] = target

    # ------------------------------------------------------------------ sabotage

    def _handle_sabotage(self, user_id: str, payload: dict):
        if self.phase != "playing":
            return
        if self.roles.get(user_id) != "impostor":
            return
        if not self.is_alive.get(user_id):
            return

        sab_type = payload.get("type")
        if sab_type == "lights":
            if self._lights_out:
                return
            cooldown = self._sabotage_timers.get("lights_cooldown", 0)
            if cooldown > 0:
                return
            self._lights_out = True
            self._sabotage_timers["lights"] = 20.0
            self._sabotage_timers["lights_cooldown"] = 45.0
            asyncio.create_task(self._broadcast_event("sabotage", {
                "type": "lights",
                "active": True,
                "duration": 20.0,
            }))
        elif sab_type == "fix_lights":
            if self.roles.get(user_id) != "crewmate":
                return
            if not self._lights_out:
                return
            self._lights_out = False
            self._sabotage_timers["lights"] = 0
            asyncio.create_task(self._broadcast_event("sabotage", {
                "type": "lights",
                "active": False,
            }))

    # ------------------------------------------------------------------ win conditions

    async def _check_win_async(self):
        result = self._check_winner()
        if result:
            await self._end_game(result)

    def _check_winner(self):
        if self._task_total > 0 and self._task_done >= self._task_total:
            return "crewmates"

        alive_crewmates = sum(
            1 for pid in self.alive_players
            if self.roles.get(pid) == "crewmate" and self.is_alive.get(pid)
        )
        alive_impostors = sum(
            1 for pid in self.alive_players
            if self.roles.get(pid) == "impostor" and self.is_alive.get(pid)
        )

        if alive_impostors == 0:
            return "crewmates"
        if alive_impostors >= alive_crewmates and alive_crewmates > 0:
            return "impostors"
        return None

    async def _end_game(self, winner: str):
        impostors = [pid for pid, r in self.roles.items() if r == "impostor"]
        await ws_manager.broadcast({
            "type": "game_over",
            "data": {
                "session_id": self.session_id,
                "winner": winner,
                "impostors": impostors,
            },
        })
        self.is_running = False
        self.phase = "ended"

    # ------------------------------------------------------------------ broadcast helpers

    async def _broadcast_event(self, event: str, payload: dict):
        await ws_manager.broadcast({
            "type": "among_us_event",
            "data": {"session_id": self.session_id, "event": event, **payload},
        })

    # ------------------------------------------------------------------ main loop

    async def _run_rounds(self, db_factory):
        players = list(self.alive_players)
        for i, pid in enumerate(players):
            self.display_names[pid] = pid
            spawn = self._map_spawns[i % len(self._map_spawns)]
            self.positions[pid] = {"x": float(spawn[0]) + 0.5, "y": float(spawn[1]) + 0.5}

        self._assign_roles()
        self._assign_tasks()

        impostors = [pid for pid, r in self.roles.items() if r == "impostor"]
        for pid in impostors:
            await ws_manager.send_personal_message({
                "type": "among_us_role",
                "data": {"session_id": self.session_id, "role": "impostor"},
            }, pid)
        crewmates = [pid for pid, r in self.roles.items() if r == "crewmate"]
        for pid in crewmates:
            await ws_manager.send_personal_message({
                "type": "among_us_role",
                "data": {
                    "session_id": self.session_id,
                    "role": "crewmate",
                    "tasks": self.tasks_assigned.get(pid, []),
                },
            }, pid)

        print(f"🕵️  [{self.game_type}] Roles assigned: {len(impostors)} impostor(s), {len(crewmates)} crewmate(s)")

        await self._broadcast_countdown()
        self.phase = "playing"

        dt = self._tick
        while self.is_running:
            if self.phase == "playing":
                await self._process_queued_inputs()
                self._update_cooldowns(dt)
                if self._frame % self._cfg_int("state_broadcast_interval_ticks") == 0:
                    await self._broadcast_state()
                self._update_task_timers(dt)
            elif self.phase == "meeting":
                await self._update_meeting(dt)

            self._frame += 1
            await asyncio.sleep(dt)

    def _update_task_timers(self, dt: float):
        for user_id, timer in list(self._task_timers.items()):
            task_def = TASK_ZONES.get(timer["task_id"])
            if not task_def:
                continue
            if task_def["type"] in ("button_press", "swipe_card", "upload_data"):
                timer["remaining"] -= dt
                if timer["remaining"] <= 0:
                    self._task_timers.pop(user_id, None)

    # ------------------------------------------------------------------ handle_player_input (called from main.py WebSocket)

    async def handle_player_input(self, msg_type: str, user_id: str, payload: dict):
        if not self.is_running:
            return
        if user_id not in self.alive_players:
            return
        self._input_queue.put_nowait((msg_type, user_id, payload))

    # ------------------------------------------------------------------ cleanup

    async def stop(self):
        self.is_running = False
        if self.task and not self.task.done():
            self.task.cancel()
