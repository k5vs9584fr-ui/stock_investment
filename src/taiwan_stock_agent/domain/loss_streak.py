from __future__ import annotations


def loss_streak_multiplier(consecutive_losses: int) -> float:
    if consecutive_losses >= 4:
        return 0.35
    if consecutive_losses == 3:
        return 0.50
    if consecutive_losses == 2:
        return 0.70
    if consecutive_losses == 1:
        return 0.85
    return 1.0
