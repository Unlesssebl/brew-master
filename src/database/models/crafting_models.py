from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.models import Base

if TYPE_CHECKING:
    from .core_models import Player


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("malt_pct BETWEEN 0 AND 100", name="chk_malt_range"),
        CheckConstraint("water_pct BETWEEN 0 AND 100", name="chk_water_range"),
        CheckConstraint("hop_pct BETWEEN 0 AND 100", name="chk_hop_range"),
        CheckConstraint("yeast_pct BETWEEN 0 AND 100", name="chk_yeast_range"),
        CheckConstraint("strength BETWEEN 0.00 AND 20.00", name="chk_beer_strength"),
        CheckConstraint("bitterness BETWEEN 0.00 AND 20.00", name="chk_beer_bitterness"),
        CheckConstraint("aroma BETWEEN 0.00 AND 20.00", name="chk_beer_aroma"),
        CheckConstraint("stability BETWEEN 0 AND 100", name="chk_beer_stability"),
        CheckConstraint(
            "malt_pct + water_pct + hop_pct + yeast_pct = 100",
            name="chk_total_proportions_100",
        ),
        Index("idx_recipes_stats_search", "strength", "bitterness", "aroma"),
        {"schema": "crafting"},
    )

    recipe_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    creator_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(150), nullable=False)

    malt_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    water_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    hop_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    yeast_pct: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    strength: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    bitterness: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    aroma: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    stability: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    is_fake: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    creator: Mapped["Player | None"] = relationship(back_populates="recipes")
    patents: Mapped[list["Patent"]] = relationship(back_populates="recipe")
    batches: Mapped[list["Batch"]] = relationship(back_populates="recipe")


class Patent(Base):
    __tablename__ = "patents"
    __table_args__ = (
        Index(
            "idx_patents_active",
            "player_id",
            postgresql_where=text("is_active = TRUE"),
        ),
        {"schema": "crafting"},
    )

    patent_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    recipe_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crafting.recipes.recipe_id"),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    daily_tax_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("50.00")
    )
    royalty_earned_24h: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0.00")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="patents")
    recipe: Mapped["Recipe"] = relationship(back_populates="patents")


class Batch(Base):
    __tablename__ = "batches"
    __table_args__ = (
        CheckConstraint("quantity_barrels >= 0", name="chk_batch_quantity"),
        Index(
            "idx_batches_player_inventory",
            "player_id",
            postgresql_where=text("quantity_barrels > 0"),
        ),
        Index(
            "idx_batches_uncompleted",
            "ready_at",
            postgresql_where=text("is_completed = FALSE"),
        ),
        {"schema": "crafting"},
    )

    batch_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    player_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("core.players.player_id", ondelete="CASCADE"),
        nullable=False,
    )
    recipe_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("crafting.recipes.recipe_id"),
        nullable=False,
    )
    quantity_barrels: Mapped[int] = mapped_column(Integer, nullable=False)
    quality_modifier: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("1.00")
    )

    is_completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ready_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    player: Mapped["Player"] = relationship(back_populates="batches")
    recipe: Mapped["Recipe"] = relationship(back_populates="batches")
