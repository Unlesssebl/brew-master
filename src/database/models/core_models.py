import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    JSON,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base

if TYPE_CHECKING:
    from .crafting_models import Batch, Patent, Recipe


class TavernTier(enum.StrEnum):
    garage = "garage"
    tavern = "tavern"
    brewery = "brewery"
    factory = "factory"
    guild = "guild"


class StaffRole(enum.StrEnum):
    master_alchemist = "master_alchemist"
    caravaner = "caravaner"
    merchant = "merchant"


class StaffStatus(enum.StrEnum):
    healthy = "healthy"
    light_injured = "light_injured"
    heavy_injured = "heavy_injured"
    dead = "dead"


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        CheckConstraint("gold >= 0", name="chk_player_gold"),
        CheckConstraint("prestige_crystals >= 0", name="chk_player_crystals"),
        CheckConstraint("reputation BETWEEN -100 AND 100", name="chk_player_reputation"),
        CheckConstraint("influence BETWEEN 0 AND 100", name="chk_player_influence"),
        CheckConstraint("suspicion BETWEEN 0 AND 100", name="chk_player_suspicion"),
        Index("idx_players_tg_id", "tg_id"),
        {"schema": "core"},
    )

    player_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    hud_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    nav_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
    gold: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("1000.00")
    )
    prestige_crystals: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reputation: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    influence: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    suspicion: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    tavern_level: Mapped[TavernTier] = mapped_column(
        PG_ENUM(TavernTier, name="tavern_tier", schema="core"),
        nullable=False,
        default=TavernTier.garage,
    )
    tutorial_step: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )
    last_offline_calc_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    staff: Mapped[list["Staff"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    resources: Mapped[list["Resource"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    recipes: Mapped[list["Recipe"]] = relationship(
        back_populates="creator",
        passive_deletes=True,
    )
    patents: Mapped[list["Patent"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    batches: Mapped[list["Batch"]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Staff(Base):
    __tablename__ = "staff"
    __table_args__ = (
        CheckConstraint("skill BETWEEN 1 AND 100", name="chk_staff_skill"),
        CheckConstraint("loyalty BETWEEN 0 AND 100", name="chk_staff_loyalty"),
        CheckConstraint("fatigue BETWEEN 0 AND 100", name="chk_staff_fatigue"),
        Index("idx_staff_player_id", "player_id"),
        {"schema": "core"},
    )

    staff_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[StaffRole] = mapped_column(
        PG_ENUM(StaffRole, name="staff_role", schema="core"), nullable=False
    )
    skill: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    loyalty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    fatigue: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[StaffStatus] = mapped_column(
        PG_ENUM(StaffStatus, name="staff_status", schema="core"),
        nullable=False,
        default=StaffStatus.healthy,
    )
    blocked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="staff")


class Resource(Base):
    __tablename__ = "resources"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="chk_resource_qty"),
        {"schema": "core"},
    )

    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="CASCADE"),
        primary_key=True,
    )
    resource_type: Mapped[str] = mapped_column(String(20), primary_key=True)
    quantity: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="resources")


class PlayerEventLog(Base):
    __tablename__ = "player_events_log"
    __table_args__ = (
        Index("idx_player_events_player_id", "player_id"),
        {"schema": "core"},
    )

    log_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    player: Mapped["Player"] = relationship()
