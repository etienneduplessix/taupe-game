from typing import Dict, Set
from fastapi import FastAPI, Depends, HTTPException, Response, Request, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update

import asyncio
from config import settings
from database import get_db, engine
from models import Base, User, Session as GameSession
from auth_service import oauth_42
from session import create_session_token, decode_session_token
from websocket_manager import ws_manager
from game_loop import start_game, active_games
from admin_router import router as admin_router

app = FastAPI(title="Taupe Typing Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(admin_router)

# Per-session waiting queues (user_ids). Populated when players connect via
# /ws?sessionId=… before the admin hits start; consumed by the start endpoint.
session_queues: Dict[str, Set[str]] = {}


async def broadcast_queue_update(session_id: str):
    await ws_manager.broadcast({
        "type": "queue_update",
        "data": {
            "session_id": session_id,
            "count": len(session_queues.get(session_id, set())),
        }
    })

@app.on_event("startup")
async def startup():
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Idempotently add coalition columns to existing users table (Postgres)
        for stmt in [
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS ft_user_id BIGINT",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coalition_id INTEGER",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coalition_name VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coalition_slug VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coalition_color VARCHAR",
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS coalition_image_url VARCHAR",
            "CREATE INDEX IF NOT EXISTS ix_users_ft_user_id ON users (ft_user_id)",
            "CREATE INDEX IF NOT EXISTS ix_users_coalition_id ON users (coalition_id)",
        ]:
            await conn.execute(text(stmt))

    # Start the Redis event listener in the background
    asyncio.create_task(ws_manager.listen_for_events())

@app.on_event("shutdown")
async def shutdown():
    # Cleanup game loops
    for game in active_games.values():
        await game.stop()

# --- Authentication Endpoints ---
# ... [Same as before]

# --- Authentication Endpoints ---

@app.get("/api/auth/login")
async def login():
    url = await oauth_42.get_authorization_url()
    return {"url": url}

@app.get("/api/auth/callback")
async def auth_callback(code: str, response: Response, db: AsyncSession = Depends(get_db)):
    try:
        token = await oauth_42.get_access_token(code)
        user_info = await oauth_42.get_user_info(token)
        ft_login = user_info.get("login")
        ft_user_id = user_info.get("id")

        if not ft_login:
            raise HTTPException(status_code=400, detail="Login not found in user info")

        result = await db.execute(select(User).where(User.ft_login == ft_login))
        user = result.scalars().first()

        if not user:
            user = User(
                ft_login=ft_login,
                ft_user_id=ft_user_id,
                display_name=user_info.get("display_name", ft_login),
                avatar_url=user_info.get("avatar_url"),
                is_admin=ft_login in settings.admin_list
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            user.is_admin = ft_login in settings.admin_list
            if ft_user_id and not user.ft_user_id:
                user.ft_user_id = ft_user_id
            await db.commit()

        # Fetch coalition info (best-effort; falls back silently)
        coalitions = await oauth_42.get_user_coalitions(ft_user_id or ft_login)
        if coalitions:
            c = coalitions[0]
            user.coalition_id = c.get("id")
            user.coalition_name = c.get("name")
            user.coalition_slug = c.get("slug")
            user.coalition_color = c.get("color")
            user.coalition_image_url = c.get("image_url")
            await db.commit()

        token_str = create_session_token(user.id)
        redirect = RedirectResponse(url="/", status_code=303)
        redirect.set_cookie(
            key="session",
            value=token_str,
            httponly=True,
            samesite="lax",
        )
        return redirect
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@app.get("/api/me")
async def get_me(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("session")
    if not token:
        return None
        
    user_id = decode_session_token(token)
    if not user_id:
        return None
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    
    if not user:
        return None
        
    return {
        "id": user.id,
        "login": user.ft_login,
        "display_name": user.display_name,
        "avatar_url": user.avatar_url,
        "is_admin": user.is_admin,
        "coalition": {
            "id": user.coalition_id,
            "name": user.coalition_name,
            "slug": user.coalition_slug,
            "color": user.coalition_color,
            "image_url": user.coalition_image_url,
        } if user.coalition_id else None,
    }

# --- Game Infrastructure ---

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    # 1. Authenticate via cookie
    token = websocket.cookies.get("session")
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = decode_session_token(token)
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    session_id = websocket.query_params.get("sessionId")

    # Load user display info for chat
    from database import async_session
    display_name = user_id
    login = user_id
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        u = result.scalars().first()
        if u:
            display_name = u.display_name or u.ft_login
            login = u.ft_login

    # 2. Register connection
    await ws_manager.connect(user_id, websocket)

    # 3. Either join the running game or sit in the session's waiting queue
    joined_running_game = False
    if session_id:
        running_game = active_games.get(session_id)
        if running_game and running_game.is_running:
            await running_game.add_player(user_id)
            joined_running_game = True
        else:
            session_queues.setdefault(session_id, set()).add(user_id)
            await broadcast_queue_update(session_id)
            await ws_manager.send_personal_message({
                "type": "queue_joined",
                "data": {
                    "session_id": session_id,
                    "count": len(session_queues[session_id]),
                }
            }, user_id)

    # Fallback: also try any other running game (legacy single-game flows)
    if not joined_running_game:
        for game in active_games.values():
            if game.is_running:
                await game.add_player(user_id)
                break

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "taupe_attempt":
                payload = data.get("data") or {}
                if isinstance(payload.get("key"), str):
                    payload["key"] = payload["key"].upper()
                print(f"User {user_id} attempted round {payload.get('round_id')} with key {payload.get('key')}")
                # Find the game this user is in and dispatch the attempt.
                for game in active_games.values():
                    if user_id in game.alive_players:
                        await game.process_attempt(user_id, payload)
                        break

            elif msg_type == "chat_message":
                import time as _t
                payload = data.get("data") or {}
                text = (payload.get("text") or "").strip()[:300]
                if not text:
                    continue
                await ws_manager.broadcast({
                    "type": "chat",
                    "data": {
                        "session_id": payload.get("session_id"),
                        "user_id": user_id,
                        "login": login,
                        "display_name": display_name,
                        "text": text,
                        "ts": int(_t.time() * 1000),
                    }
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(user_id)
        for game in list(active_games.values()):
            if user_id in game.alive_players:
                await game.remove_player(user_id)
        # Remove from any queue they were sitting in
        for sid, queue in list(session_queues.items()):
            if user_id in queue:
                queue.discard(user_id)
                await broadcast_queue_update(sid)

@app.post("/api/admin/sessions/start")
async def start_game_endpoint(session_id: str, db: AsyncSession = Depends(get_db)):
    # This is a simplified start point. In a full version, we'd check admin rights.
    async def db_factory():
        # This is a hack to provide a session factory to the game loop
        # in a real app we'd use a more robust DI pattern
        from .database import async_session
        return async_session()

    await start_game(session_id, db_factory)
    return {"status": "game started"}

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# --- Public session info (used by the player lobby + play page) ---

def _public_session(s, queue_count: int) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "status": s.status,
        "queue_count": queue_count,
        "config_json": {
            "keyboard_layout": (s.config_json or {}).get("keyboard_layout", "QWERTY"),
        },
    }


@app.get("/api/sessions")
async def list_public_sessions(db: AsyncSession = Depends(get_db)):
    """Sessions joinable by players (waiting + running)."""
    result = await db.execute(
        select(GameSession).where(GameSession.status.in_(["waiting", "running"]))
    )
    sessions = result.scalars().all()
    return [_public_session(s, len(session_queues.get(s.id, set()))) for s in sessions]


@app.get("/api/sessions/{session_id}")
async def get_public_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    s = result.scalars().first()
    if not s:
        raise HTTPException(status_code=404, detail="Session not found")
    return _public_session(s, len(session_queues.get(s.id, set())))

@app.get("/api/debug/start-game")
async def debug_start_game():
    """Debug endpoint to start a test game (development only)"""
    session_id = "debug-session"
    if session_id not in active_games:
        from database import async_session
        def db_factory():
            return async_session()
        await start_game(session_id, db_factory)
    return {"status": "game started", "session_id": session_id}

@app.get("/api/debug/get-session")
async def debug_get_session(response: Response, db: AsyncSession = Depends(get_db)):
    """Debug endpoint to get a test admin session token (development only)"""
    ft_login = "debug-admin"
    result = await db.execute(select(User).where(User.ft_login == ft_login))
    user = result.scalars().first()
    if not user:
        user = User(
            ft_login=ft_login,
            display_name="Debug Admin",
            is_admin=True,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
    else:
        user.is_admin = True
        await db.commit()

    token_str = create_session_token(user.id)
    response.set_cookie(
        key="session",
        value=token_str,
        httponly=True,
        samesite="lax",
    )
    return {"status": "session created", "user_id": user.id, "is_admin": True}
