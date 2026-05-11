# Implementation Plan - Taupe Typing

This plan outlines the steps to implement the Taupe Typing game, transitioning from a prototype to a production-ready school LAN deployment.

## Milestone 1: Infrastructure & Foundation
Goal: Establish the basic environment and connectivity.

- [ ] Setup project directory structure.
- [ ] Create `docker-compose.yml` with Caddy, Backend (FastAPI), Frontend (Nuxt 3), Postgres, and Redis.
- [ ] Configure Caddy for reverse proxy routing (`/api` and `/ws` to backend, all others to frontend).
- [ ] Implement basic FastAPI "Hello World" endpoint.
- [ ] Implement basic Nuxt 3 "Hello World" page.
- [ ] Verify all services are healthy and communicating via Docker bridge network.
- [ ] Setup `.env` template with all required variables.

## Milestone 2: Authentication (42 OAuth)
Goal: Secure the application and identify users.

- [ ] Implement 42 OAuth flow in Backend:
    - `/api/auth/login` redirect.
    - `/api/auth/callback` token exchange and user upsert.
    - Session cookie management (`HttpOnly`, `SameSite=Lax`).
- [ ] Implement `/api/me` endpoint for authentication checks.
- [ ] Implement Admin role detection based on `ADMIN_LOGINS` whitelist.
- [ ] Create Nuxt login page and auth state management (Pinia).
- [ ] Implement auth guards on frontend for `/admin` and `/play`.

## Milestone 3: Core Game Engine (Authoritative loop)
Goal: Synchronize a single movement across multiple clients.

- [ ] Implement WebSocket connection handler in FastAPI using `redis-py` for pub/sub.
- [ ] Implement the Backend Game Loop:
    - Session state machine (`waiting` $\to$ `running` $\to$ `ended`).
    - Random key selection from configured set.
    - High-precision `taupe_spawn` broadcast.
- [ ] Implement `taupe_attempt` handler:
    - Server-side timestamping for latency measurement.
    - Basic hit/miss validation.
- [ ] Create a basic "Play" view in Nuxt that renders the target key and sends attempts.
- [ ] Test synchronization with multiple browser tabs.

## Milestone 4: Frontend Gameplay Experience
Goal: Make the game feel like a game.

- [ ] Build the Virtual QWERTY Keyboard component in Nuxt.
- [ ] Implement visual "pop-up" animations for taupes on the keyboard.
- [ ] Add visual/auditory feedback for Hits, Misses, and Timeouts.
- [ ] Implement a "Lobby" view showing player count and waiting state.
- [ ] Create the "Eliminated" screen with a placeholder for stats.
- [ ] Create the "Winner" celebration screen.

## Milestone 5: Scoring & Elimination Logic
Goal: Implement the competitive mechanics.

- [ ] Implement scoring formulas:
    - Latency-based point calculation.
    - Combo multipliers (5/10/20 consecutive hits).
    - Miss penalties.
- [ ] Implement Elimination Rules:
    - Speed elimination: Rolling average reaction time.
    - Mistake elimination: Max mistakes threshold (total or rolling).
    - Disconnect elimination: Immediate removal on WS close.
- [ ] Implement `player_eliminated` event and state update.
- [ ] Persist scores and attempts to PostgreSQL in batches to avoid hot-path bottlenecks.

## Milestone 6: Dynamic Scaling & Refinement
Goal: Ensure the game intensity ramps up.

- [ ] Implement the Dynamic Speed Scaling calculation:
    - calculate `current_interval` and `current_timeout` based on $\text{alive\_count} / \text{initial\_count}$.
    - Apply scaling exponent $k$.
- [ ] Integrate scaling into the authoritative game loop.
- [ ] Implement "Sudden Death" manual trigger.
- [ ] Refine the game end condition (exactly 1 player remaining).

## Milestone 7: Admin Dashboard
Goal: Give staff full control over the event.

- [ ] Build the Session Management UI:
    - Create/Edit session configuration (JSON blob).
    - Start, Pause, Resume, Force-end buttons.
- [ ] Implement the Live Monitoring Dashboard:
    - Alive count, current round number.
    - Top 10 live scores.
    - Current speed/timeout values.
- [ ] Implement the "Kick Player" functionality.
- [ ] Create the Post-Session Scoreboard view with detailed stats.
- [ ] Implement CSV export for final results.

## Milestone 8: Final Polish & Deployment Prep
Goal: Stability and "Day 1" readiness.

- [ ] Implement rate-limiting on `taupe_attempt` events.
- [ ] Add comprehensive structured logging (JSON) for session events.
- [ ] Run load tests with simulated clients (up to 200).
- [ ] Perform "dry run" tests on actual school wifi (latency checks).
- [ ] Finalize the Pre-Event Checklist (Static IP, Firewall, etc.).
- [ ] Documentation for staff on how to run the stack.
