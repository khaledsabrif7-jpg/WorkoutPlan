"""Improved meal selector using beam search, dietary filters and macro scoring.

V3 changes:
- Supports 3, 4 and 5 meal plans.
- Uses high-calorie snack slots for gain/bulk plans.
- Applies a stronger diversity penalty to reduce repeated protein sources.
- Gives gain/bulk plans a small bias toward bulking/high-calorie meals.
"""
from __future__ import annotations

import random
from collections import defaultdict
from typing import Optional

from meals_db import MEALS_DB, MealRecord

GOAL_MACRO_RATIOS: dict[str, dict[str, float]] = {
    "lose": {"protein": 0.40, "carbs": 0.35, "fat": 0.25},
    "maintain": {"protein": 0.30, "carbs": 0.40, "fat": 0.30},
    "gain": {"protein": 0.30, "carbs": 0.50, "fat": 0.20},
}

# For gain/bulk we now use snacks automatically from main.py, but the selector
# itself supports all meal counts so the older API can use them too.
MEAL_TYPE_PLANS: dict[int, list[str]] = {
    3: ["breakfast", "lunch", "dinner"],
    4: ["breakfast", "lunch", "snack", "dinner"],
    5: ["breakfast", "snack", "lunch", "snack", "dinner"],
}

MEAL_CALORIE_SHARE_BY_COUNT: dict[int, list[float]] = {
    3: [0.25, 0.40, 0.35],
    4: [0.22, 0.33, 0.15, 0.30],
    5: [0.20, 0.12, 0.32, 0.12, 0.24],
}


def normalize_preference(value: Optional[str]) -> str:
    if not value:
        return "normal"
    v = value.strip().lower().replace("_", " ").replace("-", " ")
    mapping = {
        "none": "normal", "all": "normal", "balanced": "normal", "normal": "normal",
        "vegetarian": "vegetarian", "vegan": "vegan", "pescatarian": "pescatarian",
        "keto": "low_carb", "low carb": "low_carb", "high protein": "high_protein",
        "dairy free": "dairy_free", "gluten free": "gluten_free",
    }
    return mapping.get(v, v.replace(" ", "_"))


def meal_allowed(meal: MealRecord, dietary_preference: Optional[str]) -> bool:
    pref = normalize_preference(dietary_preference)
    if pref == "normal":
        return True
    tags = set(meal.get("dietary_tags", []))
    if pref == "pescatarian":
        return "pescatarian" in tags or "vegetarian" in tags or "vegan" in tags
    return pref in tags


def _eval_combination(
    comb: list[MealRecord],
    target_calories: float,
    target_p: float,
    target_c: float,
    target_f: float,
    strategy: str,
    goal: str,
    shares: list[float],
) -> float:
    if not comb:
        return 0.0

    # Use the exact planned slot shares instead of a generic meal-type share.
    share = sum(shares[: len(comb)]) if shares else min(1.0, len(comb) / 3)
    tc = max(target_calories * share, 1)
    tp = max(target_p * share, 1)
    tcb = max(target_c * share, 1)
    tf = max(target_f * share, 1)

    cal = sum(m["calories"] for m in comb)
    p = sum(m["protein"] for m in comb)
    carbs = sum(m["carbs"] for m in comb)
    fat = sum(m["fat"] for m in comb)

    error = (
        abs(cal - tc) / tc
        + 2.5 * abs(p - tp) / tp
        + abs(carbs - tcb) / tcb
        + abs(fat - tf) / tf
    )

    # Stronger diversity penalty: same protein source should not dominate a day.
    sources = [m.get("protein_source", m["name"]) for m in comb]
    duplicate_sources = len(sources) - len(set(sources))
    error += duplicate_sources * 0.85

    # Avoid repeating the same visual/meal style too much.
    names = [m["name"].split()[0:2] for m in comb]
    duplicate_name_families = len(names) - len({tuple(n) for n in names})
    error += duplicate_name_families * 0.25

    if any(not m.get("image") for m in comb):
        error += 0.25

    tags = [tag for meal in comb for tag in meal.get("dietary_tags", [])]
    if goal == "gain":
        # Encourage higher-calorie and bulking meals/snacks for gain cases.
        error -= 0.12 * tags.count("bulking")
        if len(comb) >= 4 and any(m["meal_type"] == "snack" and m["calories"] >= 450 for m in comb):
            error -= 0.20
    elif goal == "lose":
        error -= 0.08 * tags.count("cutting")

    fitness = -error
    if strategy == "flexible":
        fitness += random.uniform(-0.04, 0.04)
    return fitness


def _candidate_priority(meal: MealRecord, goal: str) -> float:
    tags = set(meal.get("dietary_tags", []))
    score = 0.0
    if goal == "gain":
        score += 2.0 if "bulking" in tags else 0.0
        score += meal["calories"] / 500.0
        score += meal["protein"] / 70.0
    elif goal == "lose":
        score += 1.5 if "cutting" in tags else 0.0
        score += meal["protein"] / max(meal["calories"], 1) * 4
    else:
        score += 1.0 if 350 <= meal["calories"] <= 750 else 0.0
    return score


def select_meals(
    num_meals: int,
    daily_calories: float,
    goal: str,
    strategy: str = "strict",
    dietary_preference: Optional[str] = None,
    seed: Optional[int] = None,
) -> list[dict]:
    if seed is not None:
        random.seed(seed)

    num_meals = 5 if num_meals >= 5 else 4 if num_meals == 4 else 3
    meal_types = MEAL_TYPE_PLANS[num_meals]
    shares = MEAL_CALORIE_SHARE_BY_COUNT[num_meals]
    ratios = GOAL_MACRO_RATIOS[goal]
    target_p = (daily_calories * ratios["protein"]) / 4
    target_c = (daily_calories * ratios["carbs"]) / 4
    target_f = (daily_calories * ratios["fat"]) / 9

    pool: dict[str, list[MealRecord]] = defaultdict(list)
    for meal in MEALS_DB:
        if meal_allowed(meal, dietary_preference):
            pool[meal["meal_type"]].append(meal)

    # Fallback if preference is too strict.
    if any(len(pool.get(slot, [])) < 5 for slot in set(meal_types)):
        pool = defaultdict(list)
        for meal in MEALS_DB:
            pool[meal["meal_type"]].append(meal)

    for slot in pool:
        pool[slot].sort(key=lambda m: _candidate_priority(m, goal), reverse=True)

    beams: list[list[MealRecord]] = [[]]
    beam_width = 90 if strategy == "strict" else 110
    for slot in meal_types:
        candidates = pool.get(slot, [])
        if not candidates:
            continue
        # Keep enough candidates for optimization, but avoid exploding runtime.
        candidates = candidates[:85] if goal == "gain" else candidates[:70]
        new_beams: list[tuple[float, list[MealRecord]]] = []
        for beam in beams:
            used_names = {m["name"] for m in beam}
            used_sources = {m.get("protein_source") for m in beam}
            for meal in candidates:
                if meal["name"] in used_names:
                    continue
                candidate = beam + [meal]
                score = _eval_combination(candidate, daily_calories, target_p, target_c, target_f, strategy, goal, shares)
                # Soft bonus for a new protein source to reduce repetition.
                if meal.get("protein_source") not in used_sources:
                    score += 0.18
                new_beams.append((score, candidate))
        new_beams.sort(key=lambda x: x[0], reverse=True)
        beams = [b for _, b in new_beams[:beam_width]]
    return [dict(m) for m in (beams[0] if beams else [])]
