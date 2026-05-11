# Taupe Typing - Technical Specification

This document provides the detailed technical specifications for the implementation of Taupe Typing, based on the high-level Project Plan.

## 1. Database Schema (PostgreSQL)

### Users
- `id`: UUID (PK)
- `ft_login`: String (Unique, Indexed)
- `display_name`: String
- `avatar_url`: String
- `is_admin`: Boolean (Default: false)
- `created_at`: Timestamp

### Sessions
- `id`: UUID (PK)
- `name`: String
- `config_json`: JSONB (Stores all scoring, elimination, and scaling parameters)
- `status`: Enum (`waiting`, `running`, `ended`)
- `created_by`: UUID (FK $\to$ Users.id)
- `started_at`: Timestamp (Nullable)
- `ended_at`: Timestamp (Nullable)
- `initial_player_count`: Integer
- `winner_user_id`: UUID (FK $\to$ Users.id, Nullable)

### Rounds
- `id`: UUID (PK)
- `session_id`: UUID (FK $\to$ Sessions.id)
- `round_number`: Integer
- `target_key`: Char(1)
- `spawn_ts`: Timestamp (High precision)
- `timeout_ms`: Integer
- `interval_ms`: Integer

### Attempts
- `id`: BigInt (PK)
- `round_id`: UUID (FK $\to$ Rounds.id)
- `user_id`: UUID (FK $\to$ Users.id)
- `pressed_key`: Char(1)
- `latency_ms`: Integer
- `outcome`: Enum (`hit`, `miss`, `timeout`)

### SessionScores
- `session_id`: UUID (FK $\to$ Sessions.id)
- `user_id`: UUID (FK $\to$ Users.id)
- `final_score`: Integer
- `hits`: Integer
- `misses`: Integer
- `timeouts`: Integer
- `avg_latency_ms`: Float
- `eliminated_at_round`: Integer (Nullable)
- `elimination_reason`: Enum (`speed`, `mistakes`, `disconnect`, `kicked`, `survived`)
- `final_rank`: Integer
- PK: (`session_id`, `user_id`)

---

## 2. API Endpoints (REST)

### Authentication
- `GET /api/auth/login`: Redirects to 42 OAuth
- `GET /api/auth/callback`: Handles OAuth callback, issues session cookie
- `GET /api/me`: Returns current authenticated user info

### Admin
- `POST /api/admin/sessions`: Create a new session
- `PUT /api/admin/sessions/{id}`: Update session config
- `DELETE /api/admin/sessions/{id}`: Delete a session
- `POST /api/admin/sessions/{id}/start`: Start the session
- `POST /api/admin/sessions/{id}/pause`: Pause/Resume session
- `POST /api/admin/sessions/{id}/sudden-death`: Trigger sudden death
- `POST /api/admin/sessions/{id}/end`: Force end session
- `POST /api/admin/sessions/{id}/kick/{user_id}`: Kick player
- `GET /api/admin/sessions/{id}/stats`: Live session stats

### Player
- `GET /api/sessions/active`: Get the current active session (if any)
- `GET /api/sessions/{id}/scoreboard`: Get final scoreboard for a session

---

## 3. WebSocket Protocol

Connections are established at `/ws`. A session cookie is required for authentication.

### Server $\to$ Client Events
- `session_countdown { seconds }`: Countdown before game start.
- `session_start { session_id, config }`: Game starts.
- `taupe_spawn { round_id, key, timeout_ms }`: A new taupe appears.
- `player_eliminated { reason, stats, current_rank }`: Client is out.
- `session_end { scoreboard }`: Game over, show final ranks.
- `game_paused { resume_in_ms }`: Game is temporarily paused.
- `game_resumed`: Game is back.
- `system_message { text }`: General announcement.

### Client $\to$ Server Events
- `taupe_attempt { round_id, key, client_ts }`: Player pressed a key.
- `heartbeat`: Keep-alive ping.

---

## 4. Frontend Architecture (Nuxt 3)

### Pages
- `/login`: Landing page with "Login with 42".
- `/play`: The game arena.
    - Virtual QWERTY keyboard.
    - Visual feedback for hits/misses.
    - Score and status overlays.
    - End-game scoreboard.
- `/admin`: Administration panel.
    - Session management (Create/Edit).
    - Live monitoring dashboard.
    - Post-game analysis and CSV export.

### State Management (Pinia)
- `authStore`: Manages user identity and token.
- `gameStore`: Manages local game state, current taupe, and socket connection.
- `adminStore`: Manages session configurations and live stats.

---

## 5. Infrastructure & Deployment

### Docker Compose Services
- `caddy`: Reverse proxy.
    - Port 8080 $\to$ `/api`, `/ws` $\to$ `backend`
    - Port 8080 $\to$ `/` $\to$ `frontend`
- `backend`: FastAPI app.
- `frontend`: Nuxt 3 app (Node.js output).
- `postgres`: Database.
- `redis`: Pub/Sub for WebSockets and ephemeral state.

### Network
- Single bridge network.
- Only `caddy` exposes port 8080.
- Rootless Docker.
