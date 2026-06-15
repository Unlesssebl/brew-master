"""
Модуль фоновых расчетов экономики: начисление роялти,
прогрессивный антимонопольный налог, ценообразование и насыщение рынка.
Формулы в docs/04_math_and_economy.md.
"""
import math
from enum import Enum


class FractionMultiplier(float, Enum):
    """
    Множители фракций для расчета цены сбыта.
    Гномы: 2.0, Эльфы: 0.8, Гоблины: 0.2.
    """
    DWARVES = 2.0
    GNOMES = 2.0
    ELVES = 0.8
    GOBLINS = 0.2


def calculate_patent_tax(daily_royalty: float) -> float:
    """
    Рассчитывает налог на патент.
    Формула: Tax_daily = 50 + (daily_royalty * 0.15)
    """
    tax = 50.0 + daily_royalty * 0.15
    return float(round(tax, 2))


def calculate_patent_daily_tax(royalty_24h: float) -> float:
    """
    Рассчитывает прогрессивный налог за владение патентом.
    Формула: Tax_daily = 50 + (R_24h * 0.15)
    """
    return calculate_patent_tax(royalty_24h)


def calculate_royalty_payouts(transactions: list) -> float:
    """
    Фоновый расчет начислений роялти по транзакциям за период.
    Проверяет продажи на легальном и сером рынках (market_type IN ('legal', 'grey')).
    Формула: R_total = sum(V_i * P_i * 0.05)
    """
    r_total = 0.0
    for tx in transactions:
        market_type = getattr(tx, "market_type", None)
        if market_type is None and isinstance(tx, dict):
            market_type = tx.get("market_type")
            
        if market_type in ("legal", "grey"):
            volume = getattr(tx, "volume", None)
            if volume is None and isinstance(tx, dict):
                volume = tx.get("volume", 0)
                
            price = getattr(tx, "price", None)
            if price is None and isinstance(tx, dict):
                price = tx.get("price", 0.0)
                
            r_total += (volume or 0) * (price or 0.0) * 0.05
    return float(round(r_total, 2))


def calculate_saturation_penalty(
    v_sold_ema: float,
    threshold: int,
    lambda_coef: float,
) -> float:
    """
    Рассчитывает анти-демпинговый штраф перенасыщения рынка.
    Формула: D_penalty = e^(-lambda * max(0, V - Threshold))
    Результат округляется до 4 знаков после запятой.
    """
    excess = max(0.0, v_sold_ema - threshold)
    penalty = math.exp(-lambda_coef * excess)
    return float(round(penalty, 4))


def calculate_market_saturation_penalty(
    ema_volume_sold: float,
    threshold: float = 500.0,
    elasticity_lambda: float = 0.001,
) -> float:
    """
    Рассчитывает коэффициент падения цен из-за перенасыщения рынка.
    Формула: D_penalty = e^(-lambda * max(0, EMA_volume - Threshold))
    """
    return calculate_saturation_penalty(
        v_sold_ema=ema_volume_sold,
        threshold=int(threshold),
        lambda_coef=elasticity_lambda,
    )


def calculate_final_price(
    base_price: float,
    k_market: float,
    k_quality: float,
    d_penalty: float,
) -> float:
    """
    Рассчитывает итоговую цену за бочку.
    Формула: P_final = P_base * K_market * K_quality * D_penalty
    """
    p_final = base_price * k_market * k_quality * d_penalty
    return float(round(p_final, 2))


def calculate_final_barrel_price(
    base_price: float,
    k_market: float,
    k_quality: float,
    d_penalty: float,
) -> float:
    """
    Рассчитывает финальную цену бочки пива при сбыте.
    Формула: P_final = P_base * K_market * K_quality * D_penalty
    """
    return calculate_final_price(
        base_price=base_price,
        k_market=k_market,
        k_quality=k_quality,
        d_penalty=d_penalty,
    )

