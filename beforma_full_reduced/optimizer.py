"""Macro optimizer for fitting selected meals to calorie and macro targets."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MacroTarget:
    calories: float
    protein: float
    carbs: float
    fat: float


@dataclass
class OptimizationResult:
    meals: list[dict]
    plan_totals: dict[str, float]
    scaling_factors: list[float]
    strategy_used: str
    converged: bool
    iterations: int
    error_pct: float


def _meal_scale(meal: dict, factor: float, strategy: str) -> dict:
    scaled = meal.copy()
    scaled["calories"] = round(meal.get("calories", 0) * factor, 1)
    scaled["protein"] = round(meal.get("protein", 0) * factor, 1)
    scaled["carbs"] = round(meal.get("carbs", 0) * factor, 1)
    scaled["fat"] = round(meal.get("fat", 0) * factor, 1)
    scaled["items"] = []
    for item in meal.get("items", []):
        qty = float(item.get("quantity_g", 100)) * factor
        qty = round(qty / 10) * 10 if strategy == "flexible" else round(qty, 1)
        scaled["items"].append({**item, "quantity_g": qty})
    scaled["_scale"] = round(factor, 3)
    return scaled


def _plan_totals(meals: list[dict]) -> dict[str, float]:
    return {
        "calories": round(sum(m.get("calories", 0) for m in meals), 1),
        "protein": round(sum(m.get("protein", 0) for m in meals), 1),
        "carbs": round(sum(m.get("carbs", 0) for m in meals), 1),
        "fat": round(sum(m.get("fat", 0) for m in meals), 1),
    }


def _normalized_error(totals: dict, target: MacroTarget) -> float:
    return (
        abs(totals["calories"] - target.calories) / max(target.calories, 1)
        + 1.8 * abs(totals["protein"] - target.protein) / max(target.protein, 1)
        + abs(totals["carbs"] - target.carbs) / max(target.carbs, 1)
        + abs(totals["fat"] - target.fat) / max(target.fat, 1)
    ) / 4.8


def _tolerance_ok(totals: dict, target: MacroTarget, tol: float) -> bool:
    return all([
        abs(totals["calories"] - target.calories) / max(target.calories, 1) <= tol,
        abs(totals["protein"] - target.protein) / max(target.protein, 1) <= tol * 1.5,
        abs(totals["carbs"] - target.carbs) / max(target.carbs, 1) <= tol * 1.8,
        abs(totals["fat"] - target.fat) / max(target.fat, 1) <= tol * 1.8,
    ])


def _coordinate_descent(meals: list[dict], target: MacroTarget, max_iter: int = 80, tol: float = 0.005) -> tuple[list[float], int]:
    n = len(meals)
    if n == 0:
        return [], 0
    x = [1.0] * n
    bases = [{"c": m["calories"], "p": m["protein"], "cb": m["carbs"], "f": m["fat"]} for m in meals]
    tc, tp, tcb, tf = max(target.calories, 1), max(target.protein, 1), max(target.carbs, 1), max(target.fat, 1)
    wc, wp, wcb, wf = 1.0, 2.2, 1.0, 1.0
    iterations = 0
    for _ in range(max_iter):
        iterations += 1
        max_change = 0.0
        for i in range(n):
            old = x[i]
            c_other = sum(x[j] * bases[j]["c"] for j in range(n) if j != i)
            p_other = sum(x[j] * bases[j]["p"] for j in range(n) if j != i)
            cb_other = sum(x[j] * bases[j]["cb"] for j in range(n) if j != i)
            f_other = sum(x[j] * bases[j]["f"] for j in range(n) if j != i)
            ci, pi, cbi, fi = bases[i]["c"] / tc, bases[i]["p"] / tp, bases[i]["cb"] / tcb, bases[i]["f"] / tf
            denom = wc * ci ** 2 + wp * pi ** 2 + wcb * cbi ** 2 + wf * fi ** 2
            if denom == 0:
                continue
            num = (
                wc * ci * (1 - c_other / tc)
                + wp * pi * (1 - p_other / tp)
                + wcb * cbi * (1 - cb_other / tcb)
                + wf * fi * (1 - f_other / tf)
            )
            x[i] = max(0.45, min(2.4, num / denom))
            max_change = max(max_change, abs(x[i] - old))
        if max_change < tol:
            break
    return x, iterations


def optimize_meal_plan(meals: list[dict], target: MacroTarget, strategy: str = "strict") -> OptimizationResult:
    scales, iterations = _coordinate_descent(meals, target)
    working = [_meal_scale(meals[i], scales[i], strategy) for i in range(len(meals))]
    totals = _plan_totals(working)
    error = _normalized_error(totals, target)
    tol = 0.05 if strategy == "strict" else 0.08
    return OptimizationResult(working, totals, scales, strategy, _tolerance_ok(totals, target, tol), iterations, round(error * 100, 2))
