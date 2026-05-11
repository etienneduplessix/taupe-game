from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON, BigInteger, Float, Enum as SQLAlchemyEnum
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    ft_login = Column(String, unique=True, index=True, nullable=False)
    display_name = Column(String)
    avatar_url = Column(String)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    config_json = Column(JSON, nullable=False)
    status = Column(String, default="waiting") # waiting, running, ended
    created_by = Column(String, ForeignKey("users.id"))
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    initial_player_count = Column(Integer)
    winner_user_id = Column(String, ForeignKey("users.id"), nullable=True)

class Round(Base):
    __tablename__ = "rounds"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), index=True)
    round_number = Column(Integer)
    target_key = Column(String(1))
    spawn_ts = Column(DateTime, nullable=False)
    timeout_ms = Column(Integer)
    interval_ms = Column(Integer)

class Attempt(Base):
    __tablename__ = "attempts"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    round_id = Column(String, ForeignKey("rounds.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    pressed_key = Column(String(1))
    latency_ms = Column(Integer)
    outcome = Column(String) # hit, miss, timeout

class SessionScore(Base):
    __tablename__ = "session_scores"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String, ForeignKey("sessions.id"), index=True)
    user_id = Column(String, ForeignKey("users.id"), index=True)
    final_score = Column(Integer, default=0)
    hits = Column(Integer, default=0)
    misses = Column(Integer, default=0)
    timeouts = Column(Integer, default=0)
    avg_latency_ms = Column(Float, default=0.0)
    eliminated_at_round = Column(Integer, nullable=True)
    elimination_reason = Column(String, nullable=True) # speed, mistakes, disconnect, kicked, survived
    final_rank = Column(Integer, nullable=True)
