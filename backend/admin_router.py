from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import Session as GameSession, User, Round, Attempt, SessionScore
from sqlalchemy import delete as sql_delete
from config import settings
from game_loop import active_games, start_game, DEFAULT_CONFIG

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateSessionBody(BaseModel):
    name: str
    config: Optional[dict] = None


class UpdateSessionBody(BaseModel):
    config: dict


def serialize_session(s: GameSession) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "config_json": s.config_json,
        "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "initial_player_count": s.initial_player_count,
        "winner_user_id": s.winner_user_id,
    }


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).order_by(GameSession.id.desc()))
    sessions = result.scalars().all()
    return [serialize_session(s) for s in sessions]


@router.post("/sessions")
async def create_session(body: CreateSessionBody, db: AsyncSession = Depends(get_db)):
    new_session = GameSession(
        name=body.name,
        config_json=body.config or dict(DEFAULT_CONFIG),
        status="waiting",
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return serialize_session(new_session)


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return serialize_session(session)


@router.put("/sessions/{session_id}")
async def update_session(session_id: str, body: UpdateSessionBody, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session.config_json = body.config
    await db.commit()
    await db.refresh(session)
    return serialize_session(session)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    if session_id in active_games:
        await active_games[session_id].stop()
        del active_games[session_id]

    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete dependent rows first (rounds -> attempts, plus session_scores)
    round_ids_result = await db.execute(select(Round.id).where(Round.session_id == session_id))
    round_ids = [rid for (rid,) in round_ids_result.all()]
    if round_ids:
        await db.execute(sql_delete(Attempt).where(Attempt.round_id.in_(round_ids)))
    await db.execute(sql_delete(Round).where(Round.session_id == session_id))
    await db.execute(sql_delete(SessionScore).where(SessionScore.session_id == session_id))

    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


@router.post("/sessions/{session_id}/start")
async def start_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from database import async_session

    def db_factory():
        return async_session()

    await start_game(session_id, db_factory)

    # Load config from DB into the running game
    if session_id in active_games and session.config_json:
        active_games[session_id].config = dict(session.config_json)

    session.status = "running"
    await db.commit()

    return {"status": "started"}


@router.post("/sessions/{session_id}/end")
async def end_session(session_id: str, db: AsyncSession = Depends(get_db)):
    if session_id in active_games:
        await active_games[session_id].stop()
        del active_games[session_id]

    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if session:
        session.status = "ended"
        await db.commit()

    return {"status": "ended"}


@router.get("/sessions/{session_id}/stats")
async def get_session_stats(session_id: str, db: AsyncSession = Depends(get_db)):
    if session_id not in active_games:
        return {"error": "No active game loop for this session"}

    game = active_games[session_id]
    top_scores = []
    if game.score_manager:
        sorted_scores = sorted(
            game.score_manager.scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )

        user_ids = [uid for uid, _ in sorted_scores]
        user_map = {}
        if user_ids:
            rows = await db.execute(select(User).where(User.id.in_(user_ids)))
            for u in rows.scalars().all():
                user_map[u.id] = {
                    "display_name": u.display_name or u.ft_login,
                    "login": u.ft_login,
                }

        for uid, score in sorted_scores:
            info = user_map.get(uid, {})
            top_scores.append({
                "user_id": uid,
                "display_name": info.get("display_name") or uid,
                "login": info.get("login") or uid,
                "score": score["score"],
                "hits": score["hits"],
                "misses": score["misses"],
                "eliminated": score["eliminated"],
            })

    return {
        "alive_count": len(game.alive_players),
        "current_round": game.current_round,
        "current_interval": game.config.get("base_spawn_interval_ms"),
        "current_timeout": game.config.get("base_timeout_ms"),
        "top_scores": top_scores,
    }
