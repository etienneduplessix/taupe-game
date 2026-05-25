from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from database import get_db
from models import Session as GameSession, User, Round, Attempt, SessionScore
from sqlalchemy import delete as sql_delete
from config import settings
from game_loop import active_games, start_game, DEFAULT_CONFIG, GAME_LOOPS, GAME_TYPE_TAUPE
from auth_service import oauth_42
from session import require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CreateSessionBody(BaseModel):
    name: str
    config: Optional[dict] = None


class UpdateSessionBody(BaseModel):
    config: dict


def serialize_session(s: GameSession) -> dict:
    # Local import to avoid circular import at module load
    from main import session_queues
    cfg = s.config_json or {}
    return {
        "id": s.id,
        "name": s.name,
        "config_json": cfg,
        "game_type": cfg.get("game_type", GAME_TYPE_TAUPE),
        "status": s.status,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "ended_at": s.ended_at.isoformat() if s.ended_at else None,
        "initial_player_count": s.initial_player_count,
        "winner_user_id": s.winner_user_id,
        "queue_count": len(session_queues.get(s.id, set())),
    }


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GameSession).order_by(GameSession.id.desc()))
    sessions = result.scalars().all()
    return [serialize_session(s) for s in sessions]


@router.post("/sessions")
async def create_session(body: CreateSessionBody, db: AsyncSession = Depends(get_db)):
    config = dict(body.config) if body.config else dict(DEFAULT_CONFIG)
    config.setdefault("game_type", GAME_TYPE_TAUPE)
    if config["game_type"] not in GAME_LOOPS:
        raise HTTPException(status_code=400, detail=f"Unknown game_type: {config['game_type']}")
    new_session = GameSession(
        name=body.name,
        config_json=config,
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

    new_config = dict(body.config)
    new_config.setdefault("game_type", GAME_TYPE_TAUPE)
    if new_config["game_type"] not in GAME_LOOPS:
        raise HTTPException(status_code=400, detail=f"Unknown game_type: {new_config['game_type']}")
    session.config_json = new_config
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
    from main import session_queues, broadcast_queue_update

    result = await db.execute(select(GameSession).where(GameSession.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from database import async_session

    def db_factory():
        return async_session()

    # Consume the queue for this session as the starting roster
    queued = set(session_queues.pop(session_id, set()))
    await start_game(
        session_id,
        db_factory,
        initial_players=queued,
        config=session.config_json,
    )

    # Load config from DB into the running game
    if session_id in active_games and session.config_json:
        active_games[session_id].config = {**DEFAULT_CONFIG, **session.config_json}

    session.status = "running"
    session.initial_player_count = len(queued)
    await db.commit()

    await broadcast_queue_update(session_id)

    return {"status": "started", "players": len(queued)}


@router.get("/sessions/{session_id}/queue")
async def get_session_queue(session_id: str, db: AsyncSession = Depends(get_db)):
    from main import session_queues
    user_ids = list(session_queues.get(session_id, set()))
    if not user_ids:
        return {"count": 0, "players": []}
    rows = await db.execute(select(User).where(User.id.in_(user_ids)))
    players = []
    for u in rows.scalars().all():
        players.append({
            "user_id": u.id,
            "login": u.ft_login,
            "display_name": u.display_name or u.ft_login,
            "avatar_url": u.avatar_url,
            "coalition": {
                "id": u.coalition_id,
                "name": u.coalition_name,
                "color": u.coalition_color,
                "image_url": u.coalition_image_url,
            } if u.coalition_id else None,
        })
    return {"count": len(players), "players": players}


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
    coalitions_ranking = []
    if game.score_manager:
        sorted_scores = sorted(
            game.score_manager.scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True,
        )

        user_ids = [uid for uid, _ in sorted_scores]
        user_map = {}
        users_needing_coalition = []
        if user_ids:
            rows = await db.execute(select(User).where(User.id.in_(user_ids)))
            for u in rows.scalars().all():
                user_map[u.id] = u
                if not u.coalition_id and (u.ft_user_id or u.ft_login):
                    users_needing_coalition.append(u)

        # Lazy-fetch coalition info for users who logged in before this feature
        for u in users_needing_coalition:
            coalitions = await oauth_42.get_user_coalitions(u.ft_user_id or u.ft_login)
            if coalitions:
                c = coalitions[0]
                u.coalition_id = c.get("id")
                u.coalition_name = c.get("name")
                u.coalition_slug = c.get("slug")
                u.coalition_color = c.get("color")
                u.coalition_image_url = c.get("image_url")
        if users_needing_coalition:
            await db.commit()

        coalition_totals: dict[int, dict] = {}
        for uid, score in sorted_scores:
            u = user_map.get(uid)
            display_name = (u.display_name if u else None) or (u.ft_login if u else None) or uid
            login = (u.ft_login if u else None) or uid
            coalition = None
            if u and u.coalition_id:
                coalition = {
                    "id": u.coalition_id,
                    "name": u.coalition_name,
                    "slug": u.coalition_slug,
                    "color": u.coalition_color,
                    "image_url": u.coalition_image_url,
                }
                bucket = coalition_totals.setdefault(u.coalition_id, {
                    "id": u.coalition_id,
                    "name": u.coalition_name,
                    "slug": u.coalition_slug,
                    "color": u.coalition_color,
                    "image_url": u.coalition_image_url,
                    "score": 0,
                    "player_count": 0,
                    "hits": 0,
                    "misses": 0,
                })
                bucket["score"] += score["score"]
                bucket["player_count"] += 1
                bucket["hits"] += score["hits"]
                bucket["misses"] += score["misses"]
            top_scores.append({
                "user_id": uid,
                "display_name": display_name,
                "login": login,
                "score": score["score"],
                "hits": score["hits"],
                "misses": score["misses"],
                "eliminated": score["eliminated"],
                "coalition": coalition,
            })

        coalitions_ranking = sorted(coalition_totals.values(), key=lambda c: c["score"], reverse=True)

    return {
        "alive_count": len(game.alive_players),
        "current_round": game.current_round,
        "current_interval": game.config.get("base_spawn_interval_ms"),
        "current_timeout": game.config.get("base_timeout_ms"),
        "top_scores": top_scores,
        "coalitions_ranking": coalitions_ranking,
    }
