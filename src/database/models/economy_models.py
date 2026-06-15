from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from src.database.models import Base


class TransactionLog(Base):
    __tablename__ = "transactions_log"
    __table_args__ = ({"schema": "economy"},)

    tx_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    seller_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    recipe_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    market_type: Mapped[str] = mapped_column(String(20), nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    total_revenue: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False
    )
    processed_for_royalty: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class MarketSaturation(Base):
    __tablename__ = "market_saturation"
    __table_args__ = ({"schema": "economy"},)

    market_segment: Mapped[str] = mapped_column(String(20), primary_key=True)
    volume_sold_24h: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
