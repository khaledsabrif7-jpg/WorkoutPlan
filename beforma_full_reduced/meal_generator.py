"""Meal plan orchestration: select -> optimize -> validate -> enrich."""
from __future__ import annotations
import time

from nutrition import NutritionPlan
from meal_selector import select_meals
from optimizer import optimize_meal_plan, MacroTarget
from validator import validate_plan
from recommender import get_meal_tags, suggest_substitutions

MAX_RETRIES = 5


def generate_full_meal_plan(nutrition_plan: NutritionPlan, num_meals: int = 3, strategy: str = "strict", dietary_preference: str | None = None) -> dict:
    started = time.perf_counter()
    target = MacroTarget(
        calories=nutrition_plan.daily_calories,
        protein=nutrition_plan.protein_grams,
        carbs=nutrition_plan.carbs_grams,
        fat=nutrition_plan.fat_grams,
    )
    best_result = None
    best_validation = None
    best_score = -1.0
    for attempt in range(1, MAX_RETRIES + 1):
        selected = select_meals(
            num_meals=num_meals,
            daily_calories=nutrition_plan.daily_calories,
            goal=nutrition_plan.goal,
            strategy=strategy,
            dietary_preference=dietary_preference,
            seed=attempt * 101,
        )
        result = optimize_meal_plan(selected, target, strategy=strategy)
        validation = validate_plan(result.meals, result.plan_totals, nutrition_plan.daily_calories, nutrition_plan.goal)
        if validation.score > best_score:
            best_score = validation.score
            best_result = result
            best_validation = validation
        if validation.passed and result.converged:
            break
    assert best_result is not None and best_validation is not None

    enriched = []
    for meal in best_result.meals:
        item = meal.copy()
        item["tags"] = get_meal_tags(meal["name"])
        item["substitutions"] = suggest_substitutions(meal["name"])
        enriched.append(item)

    return {
        "daily_targets": nutrition_plan.as_dict(),
        "daily_plan_totals": best_result.plan_totals,
        "meals": enriched,
        "strategy": best_result.strategy_used,
        "optimized": best_result.converged,
        "quality_score": best_validation.score,
        "accuracy": {
            "macro_error_pct": best_result.error_pct,
            "validation_score": best_validation.score,
            "note": "This is macro-matching accuracy, not medical accuracy.",
        },
        "validation": {
            "passed": best_validation.passed,
            "score": best_validation.score,
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message, "detail": i.detail} for i in best_validation.issues],
        },
        "meta": {"elapsed_ms": round((time.perf_counter()-started)*1000,1), "num_meals": num_meals, "dietary_preference": dietary_preference or "normal"},
    }
