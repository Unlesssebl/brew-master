import math
from unittest.mock import patch

import pytest

from src.core.crafting import (
    calculate_aroma,
    calculate_bitterness,
    calculate_stability,
    calculate_strength,
)


def test_calculate_strength():
    # Str = min(20.0, (M * sqrt(Y) / 15) * (1.2 - W / 100))
    # M=50, W=30, H=10, Y=10
    # Expected: (50 * sqrt(10) / 15) * (1.2 - 0.3) = (50 * 3.162277 / 15) * 0.9
    # = 10.5409255 * 0.9 = 9.48683
    result = calculate_strength(50, 30, 10, 10)
    expected = (50 * math.sqrt(10) / 15.0) * (1.2 - 30 / 100.0)
    assert result == pytest.approx(expected, rel=1e-5)

    # Test capping at 20.0
    result_capped = calculate_strength(100, 10, 0, 100)
    assert result_capped == 20.0

    # Test handling negative yeast
    assert calculate_strength(50, 30, 10, -5) == 0.0


def test_calculate_bitterness():
    # Bit = min(20.0, (H * 1.5 / sqrt(W / 10 + 1)) + M / 20)
    # M=30, W=40, H=20, Y=10
    # Expected: (20 * 1.5 / sqrt(4 + 1)) + 30 / 20 = 30 / sqrt(5) + 1.5 = 13.4164 + 1.5 = 14.9164
    result = calculate_bitterness(30, 40, 20, 10)
    expected = (20 * 1.5 / math.sqrt(40 / 10.0 + 1.0)) + 30 / 20.0
    assert result == pytest.approx(expected, rel=1e-5)

    # Test capping at 20.0
    result_capped = calculate_bitterness(100, 0, 100, 0)
    assert result_capped == 20.0


def test_calculate_aroma():
    # Aro = min(20.0, (H * 0.8 + M * 0.3 + Y * 0.2) / (1 + Bit / 20))
    # M=30, W=40, H=20, Y=10, bitterness=14.9164
    # Expected: (20 * 0.8 + 30 * 0.3 + 10 * 0.2) / (1 + 14.9164 / 20) = 27 / 1.74582 = 15.4655
    bitterness = 14.9164
    result = calculate_aroma(30, 40, 20, 10, bitterness)
    expected = (20 * 0.8 + 30 * 0.3 + 10 * 0.2) / (1.0 + bitterness / 20.0)
    assert result == pytest.approx(expected, rel=1e-5)


def test_calculate_stability():
    # St_base = 100 - 3 * |Y - 12| - 2 * max(0, W - 50)
    # Stab = min(100, max(0, St_base + floor(Skill / 2)))

    # No fatigue
    # Y=12, W=40, Skill=50, Fatigue=0 -> St_base=100, Stab=100
    assert calculate_stability(12, 40, 50, 0) == 100

    # Y=10, W=60, Skill=30, Fatigue=0
    # St_base = 100 - 6 - 20 = 74
    # Stab = min(100, 74 + 15) = 89
    assert calculate_stability(10, 60, 30, 0) == 89

    # Test fatigue > 80 and random < 0.25 (should clamp to min(30, st_base))
    # Y=12, W=40 (st_base = 100), Skill=50, Fatigue=85
    # random < 0.25 -> stab = min(30, 100) = 30
    with patch("random.random", return_value=0.1):
        assert calculate_stability(12, 40, 50, 85) == 30

    # random >= 0.25 -> stab = 100 (normal behavior)
    with patch("random.random", return_value=0.5):
        assert calculate_stability(12, 40, 50, 85) == 100
