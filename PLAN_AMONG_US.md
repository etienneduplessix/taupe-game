# Implementation Plan - Among Us (Crewmates vs Impostors)

This plan adds a third game type (`among_us`) to the taupe-game platform: a real-time 2D social deduction game inspired by Among Us, using the existing FastAPI + Redis + Nuxt stack.

## Architecture Decision: Redis-driven movement

The existing Taupe/Dot Rush games are round-based (server pushes one event per round). Among Us requires **continuous real-time movement**. The architecture choice:

- **Each client publishes position to a Redis channel at ~20Hz** (`among_us:{session_id}:positions`). Position events are `< 50 bytes` each.
- **The server subscribes to this channel and relays all positions to a fan-out channel**. All connected clients subscribe to receive everyone's position.
- **Game logic (kills, tasks, meetings, voting) remains server-authoritative** via the existing `BaseGameLoop` pattern.
- This avoids WebSocket per-player send loops blocking the event loop — the server only touches the Redis pub/sub stream, and the existing `ws_manager.listen_for_events()` pipeline fans out to all local clients.

## Milestone 1: Backend game loop skeleton

**Goal**: Register the `among_us` game type, wire up the Redis movement relay.

- [ ] Create `backend/games/among_us.py` with `AmongUsGameLoop(BaseGameLoop)`:
    - Constants: `GAME_TYPE_AMONG_US = "among_us"`
    - Game state: player positions dict, role assignments (crewmate/impostor), alive/dead/ghost tracking, task list, kill cooldowns, game phase (`playing` / `meeting`)
    - Subscribes to Redis channel `among_us:{session_id}:positions` in `_run_rounds`
    - Publishes aggregated positions to `among_us:{session_id}:state` at ~20Hz tick
    - Publishes events (kill, report, meeting, vote result, game_over) to `among_us:{session_id}:events`
    - `handle_player_input` dispatches: `among_us_move`, `among_us_kill`, `among_us_report`, `among_us_vote`, `among_us_task`
- [ ] Add `GAME_TYPE_AMONG_US` constant and register in `backend/game_loop.py`:
    - `register_game_loop(GAME_TYPE_AMONG_US, AmongUsGameLoop)`
    - Add `"among_us"` to `GAME_LOOPS`
    - Add `among_us_move` to the WebSocket dispatch in `main.py` (alongside `taupe_attempt`, `dot_click`)
- [ ] Update `backend/tests/test_game_registry.py` to assert `among_us` is registered

## Milestone 2: Game rules — roles, tasks, kills

**Goal**: Implement the full Among Us game logic server-side.

### Role assignment
- [ ] On game start: randomly assign 1-2 impostors (proportional to player count). 4-6 players = 1 impostor, 7-10 players = 2 impostors.
- [ ] Track `alive_players` (subset of all players). Dead players can still move as ghosts (visible only to other ghosts).
- [ ] Track `is_impostor: bool` and `is_alive: bool` per player.

### Tasks (crewmates)
- [ ] Define 4-5 simple task types defined as stationary zones on the map:
    - `button_press`: Stand in zone for 3 seconds
    - `wire_connect`: Click 4 numbered terminals in order (simple number sequence)
    - `swipe_card`: Stand in zone for 4 seconds
    - `upload_data`: Stand in zone for 5 seconds
    - `calibrate`: Click the zone repeatedly (3 clicks)
- [ ] Each crewmate gets a subset of tasks (total tasks / crewmate count, rounded up).
- [ ] On task completion: broadcast `task_complete` event, increment shared progress.
- [ ] Task bar: `tasks_completed / total_tasks`. When 100%, crewmates win.

### Impostor: kill mechanic
- [ ] `among_us_kill`: impostor sends target player_id. Server checks:
    - Sender is an impostor and alive
    - Target is a crewmate and alive
    - Distance between sender and target < kill_range (tile-based)
    - Kill cooldown not active (default: 25 seconds)
- [ ] On kill: target marked dead (becomes ghost), broadcast `player_dead` event, create a "dead body" at target's position
- [ ] Sabotage (optional, Milestone 2): impostor can trigger `sabotage_lights` (reduce visibility radius) or `sabotage_door` (block tile passage). Cooldown separate from kill.

### Win conditions
- [ ] Crewmates win: all tasks completed OR all impostors ejected
- [ ] Impostors win: impostor count >= crewmate count OR sabotage timer expires (if sabotage implemented)
- [ ] Check after every kill/eject.

## Milestone 3: 2D map with real-time movement

**Goal**: Frontend renders a tile-based map, players move with WASD/arrows.

### Map design (~20x15 tile grid)
- [ ] Define a JSON map schema in `frontend/assets/maps/ship.json`:
    - Tile types: `floor`, `wall`, `door`, `task_zone`
    - Task zones link to task type + position
    - Spawn positions
    - Map size in tiles (e.g., 20 columns × 15 rows)
    - Tile size rendered: ~48px
- [ ] Server loads the map config so it can validate movement (wall collision) and task zone proximity.

### Frontend: AmongUsArena.vue
- [ ] Create `frontend/components/games/AmongUsArena.vue`:
    - `<canvas>` element rendering the tile map + all player positions
    - Camera follows the local player (viewport scrolls)
    - Players rendered as colored circles with name labels + role indicator (visible to self)
    - Dead players shown as ghosts (transparent, visible only to other ghosts)
    - Dead bodies shown as icons on the floor
    - Task zones highlighted when player is near
- [ ] Keyboard listener for WASD/Arrow keys → emits `among_us_move` at ~20Hz
- [ ] Subscribes to WebSocket for:
    - `among_us_state` (all player positions, updated at tick rate)
    - `among_us_event` (kills, reports, task updates, meeting start/end, game_over)

### Network model
- [ ] Client sends `among_us_move { x, y, direction }` via WebSocket (throttled to 50ms)
- [ ] Server validates position (wall collision), updates Redis position hash
- [ ] Every ~50ms, server publishes full position snapshot to `among_us:{id}:state`
- [ ] Clients interpolate received positions for smooth rendering

## Milestone 4: Meetings and voting

**Goal**: When a body is reported, show discussion chat + voting UI.

### Reporting
- [ ] Crewmate next to a dead body can press `R` to report
- [ ] Server broadcasts `meeting_start { reporter_id, victim_id, participants }`
- [ ] All alive players enter discussion phase (30-60 seconds configurable)
- [ ] During discussion: chat is still available (reuse existing chat sidebar)

### Voting
- [ ] After discussion timer (or skip vote threshold), voting phase starts
- [ ] Each alive player votes for one player (or skip): `among_us_vote { target_id }`
- [ ] Player with most votes is ejected. Tie = no ejection.
- [ ] Server checks win condition after ejection.
- [ ] Broadcast `meeting_result { ejected_id, votes, skipped }`
- [ ] Game returns to `playing` phase.

### Frontend: meeting UI
- [ ] Overlay shown during meeting phase:
    - Discussion timer countdown
    - List of alive players with vote buttons
    - Chat panel for discussion
    - "Skip Vote" button
    - Result announcement animation

## Milestone 5: Frontend integration

**Goal**: Wire Among Us into the existing lobby, admin, and play pages.

- [ ] `frontend/pages/play.vue`:
    - Import `AmongUsArena`
    - `arenaComponent` computed: add `among_us → AmongUsArena`
    - `eliminatedFlavor` / `victoryFlavor`: add among_us variants
    - Game type detection from session config
- [ ] `frontend/pages/admin/index.vue`:
    - Add "Among Us" button in create modal (🕵️)
    - `AMONG_US_DEFAULTS` config object
    - Session card: display game-type-specific config (impostor count, map name, etc.)
- [ ] `frontend/pages/admin/edit/[id].vue`:
    - Add `{ value: 'among_us', label: 'Among Us', emoji: '🕵️' }` to `GAME_TYPES`
    - Config form: impostor count, kill cooldown, discussion duration, voting time, task count
- [ ] `frontend/pages/index.vue`:
    - `gameTypeLabel`: add among_us case (`🕵️ AMONG US`)

## Milestone 6: Tasks UI

**Goal**: Crewmates can see and complete tasks on the map.

- [ ] When a crewmate enters a task zone, show an overlay "Press E to start task"
- [ ] On `E` press → send `among_us_task_start { task_id }`
- [ ] Server tracks task progress (timer-based for `stand` tasks, multi-step for sequences)
- [ ] Frontend displays a mini-task UI:
    - `button_press`: progress bar filling over 3s
    - `wire_connect`: 4 colored terminals shown, click in correct order
    - `swipe_card`: progress bar filling over 4s
    - `upload_data`: progress bar filling over 5s
    - `calibrate`: counter (0/3), click the zone
- [ ] Task list sidebar showing completed/remaining tasks
- [ ] Shared task progress bar at top of screen

## Milestone 7: Polish & Sabotage (optional stretch)

- [ ] Ghost free-roam (no collisions, can pass through walls)
- [ ] Kill animation (brief flash/delay)
- [ ] Sabotage: lights out (reduced visibility radius for crewmates, 15s duration)
- [ ] Sabotage: door lock (target tile becomes impassable for 10s)
- [ ] Death notification sound
- [ ] Impostor vision slightly larger than crewmates
- [ ] End-game summary screen showing who won, who was impostor

## Map format (`ship.json`)

```json
{
  "name": "The Ship",
  "width": 20,
  "height": 15,
  "tile_size": 48,
  "tiles": [
    "WWWWWWWWWWWWWWWWWWWW",
    "W....W....W.......W",
    "W.T1.W.T2.W..T3..W",
    "W....W....W.......W",
    "WWWW.WW.WWW......W",
    "W......W..........W",
    "W..T4..W....T5...W",
    "W......W..........W",
    "WWWW.WW.WWW......W",
    "W....W....W.......W",
    "W.T6.W.T7.W.......W",
    "W....W....W..T8..W",
    "W.........W.......W",
    "W.........W.......W",
    "WWWWWWWWWWWWWWWWWWWW"
  ],
  "task_zones": {
    "T1": {"type": "button_press", "label": "Reactor"},
    "T2": {"type": "wire_connect", "label": "Wires"},
    "T3": {"type": "swipe_card", "label": "Admin"},
    "T4": {"type": "upload_data", "label": "Upload"},
    "T5": {"type": "calibrate", "label": "Engine"},
    "T6": {"type": "button_press", "label": "O2"},
    "T7": {"type": "wire_connect", "label": "Comms"},
    "T8": {"type": "swipe_card", "label": "Storage"}
  },
  "spawns": [
    {"x": 2, "y": 2},
    {"x": 17, "y": 2},
    {"x": 2, "y": 12},
    {"x": 17, "y": 12}
  ],
  "kill_range": 1.5,
  "report_range": 1.0
}
```

## Config defaults (`AMONG_US_DEFAULTS`)

```python
AMONG_US_DEFAULTS = {
    "game_type": "among_us",
    "min_players": 4,
    "max_players": 10,
    "impostor_count": 1,          # or "auto" (1 for 4-6, 2 for 7-10)
    "kill_cooldown_seconds": 25,
    "kill_range": 1.5,            # tile units
    "report_range": 1.0,
    "discussion_duration_seconds": 30,
    "voting_duration_seconds": 15,
    "total_tasks": 8,
    "tasks_per_crewmate": 4,
    "movement_speed_tiles_per_second": 3.0,
    "countdown_seconds": 5,
    "crewmate_vision_radius": 5,  # tiles
    "impostor_vision_radius": 6,
    "ghost_vision_radius": 8,
}
```

## WebSocket protocol additions

### Server → Client
| Event | Payload | When |
|-------|---------|------|
| `among_us_state` | `{ players: [{id, x, y, color, alive, ghost}], phase, task_progress }` | ~20Hz tick |
| `among_us_event` | `{ event: "kill"\|"report"\|"task_complete"\|"sabotage"\|... , ... }` | On game events |
| `meeting_start` | `{ reporter_id, victim_id, discussion_seconds }` | Body reported |
| `meeting_vote_phase` | `{ players: [{id, display_name}], voting_seconds }` | Voting begins |
| `meeting_result` | `{ ejected_id, votes: {voter: target}, skipped }` | Voting ends |
| `game_over_among` | `{ winner: "crewmates"\|"impostors", impostors: [id], reason }` | Game ends |

### Client → Server
| Event | Payload | When |
|-------|---------|------|
| `among_us_move` | `{ x, y }` | ~20Hz while moving |
| `among_us_kill` | `{ target_id }` | Impostor kills |
| `among_us_report` | `{}` | Report body |
| `among_us_vote` | `{ target_id \| "skip" }` | During voting |
| `among_us_task_start` | `{ task_id }` | Start task |
| `among_us_task_step` | `{ task_id, step_data }` | Task interaction |

## File summary

| File | Action |
|------|--------|
| `backend/games/among_us.py` | NEW — full game loop |
| `backend/game_loop.py` | MODIFY — add GAME_TYPE_AMONG_US, import & register |
| `backend/main.py` | MODIFY — add `among_us_*` message types to WebSocket dispatch |
| `backend/tests/test_game_registry.py` | MODIFY — add among_us to registry test |
| `frontend/components/games/AmongUsArena.vue` | NEW — canvas map, movement, tasks, meetings |
| `frontend/pages/play.vue` | MODIFY — import arena, add to computed |
| `frontend/pages/admin/index.vue` | MODIFY — create modal, defaults, session cards |
| `frontend/pages/admin/edit/[id].vue` | MODIFY — GAME_TYPES, config form |
| `frontend/pages/index.vue` | MODIFY — gameTypeLabel |
| `frontend/assets/maps/ship.json` | NEW — tile map definition |
