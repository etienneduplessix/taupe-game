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

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
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

        if not ft_login:
            raise HTTPException(status_code=400, detail="Login not found in user info")

        result = await db.execute(select(User).where(User.ft_login == ft_login))
        user = result.scalars().first()

        if not user:
            user = User(
                ft_login=ft_login,
                display_name=user_info.get("display_name", ft_login),
                avatar_url=user_info.get("avatar_url"),
                is_admin=ft_login in settings.admin_list
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
        else:
            user.is_admin = ft_login in settings.admin_list
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
        "is_admin": user.is_admin
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

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")

            if msg_type == "taupe_attempt":
                print(f"User {user_id} attempted round {data['data'].get('round_id')} with key {data['data'].get('key')}")

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
