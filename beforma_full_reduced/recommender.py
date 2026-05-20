"""Recommendation helpers: tags, substitutions and anonymous feedback-aware ranking."""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Optional

from meals_db import MEALS_DB, MealRecord

FEEDBACK_PATH = Path(os.getenv("MEAL_FEEDBACK_PATH", "/data/meal_feedback.json"))

SUBSTITUTION_MAP: dict[str, list[str]] = {
    "chicken": ["turkey", "tofu", "shrimp"],
    "turkey": ["chicken", "tofu", "tuna"],
    "beef": ["chicken", "turkey", "lentils"],
    "salmon": ["tuna", "shrimp", "tofu"],
    "tuna": ["salmon", "shrimp", "chickpeas"],
    "shrimp": ["tuna", "salmon", "tofu"],
    "tofu": ["lentils", "chickpeas", "eggs"],
    "lentils": ["chickpeas", "black beans", "tofu"],
    "dairy": ["eggs", "tofu"],
    "egg": ["greek yogurt", "tofu", "cottage cheese"],
}


def _load_feedback() -> dict:
    try:
        if FEEDBACK_PATH.exists():
            return json.loads(FEEDBACK_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {"accepted": {}, "rejected": {}, "counts": {}}


def _save_feedback(data: dict) -> None:
    try:
        FEEDBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
        FEEDBACK_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _feedback_bias(meal_name: str) -> float:
    data = _load_feedback()
    accepted = data.get("accepted", {}).get(meal_name, 0)
    rejected = data.get("rejected", {}).get(meal_name, 0)
    total = accepted + rejected
    if total == 0:
        return 0.0
    return ((accepted / total) - 0.5) * 20.0


def get_meal_tags(meal_name: str) -> list[str]:
    meal = next((m for m in MEALS_DB if m["name"] == meal_name), None)
    return list(meal.get("dietary_tags", [])) if meal else []


def rank_meals_for_goal(goal: str, meal_type: Optional[str] = None, top_n: int = 5, dietary_preference: Optional[str] = None) -> list[MealRecord]:
    from meal_selector import GOAL_MACRO_RATIOS, meal_allowed
    ratios = GOAL_MACRO_RATIOS[goal]
    def score(meal: MealRecord) -> float:
        cal = max(meal["calories"], 1)
        p_share = (meal["protein"] * 4) / cal
        c_share = (meal["carbs"] * 4) / cal
        f_share = (meal["fat"] * 9) / cal
        balance = 1.0 - (abs(p_share-ratios["protein"]) + abs(c_share-ratios["carbs"]) + abs(f_share-ratios["fat"])) / 0.75
        return balance * 100 + _feedback_bias(meal["name"])
    pool = [m for m in MEALS_DB if (meal_type is None or m["meal_type"] == meal_type) and meal_allowed(m, dietary_preference)]
    return sorted(pool, key=score, reverse=True)[:top_n]


def _meal_vector(meal: MealRecord) -> list[float]:
    cal = max(meal["calories"], 1)
    return [cal/700, (meal["protein"]*4)/cal, (meal["carbs"]*4)/cal, (meal["fat"]*9)/cal]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x,y in zip(a,b)); ma = sum(x*x for x in a) ** 0.5; mb = sum(y*y for y in b) ** 0.5
    return dot / (ma*mb) if ma and mb else 0.0


def suggest_substitutions(meal_name: str) -> list[str]:
    target = next((m for m in MEALS_DB if m["name"] == meal_name), None)
    if not target:
        return []
    similar = []
    vt = _meal_vector(target)
    for meal in MEALS_DB:
        if meal["name"] == meal_name or meal["meal_type"] != target["meal_type"]:
            continue
        similar.append((_cosine(vt, _meal_vector(meal)), meal["name"]))
    similar.sort(reverse=True)
    return [name for _, name in similar[:3]]


def record_feedback(meal_name: str, accepted: bool) -> None:
    data = _load_feedback()
    bucket = "accepted" if accepted else "rejected"
    data.setdefault(bucket, {})[meal_name] = data.setdefault(bucket, {}).get(meal_name, 0) + 1
    data.setdefault("counts", {})[meal_name] = data.setdefault("counts", {}).get(meal_name, 0) + 1
    _save_feedback(data)


def get_feedback_stats() -> dict:
    data = _load_feedback()
    meals = []
    names = set(data.get("accepted", {})) | set(data.get("rejected", {}))
    for name in names:
        a = data.get("accepted", {}).get(name, 0); r = data.get("rejected", {}).get(name, 0)
        meals.append({"meal": name, "accepted": a, "rejected": r, "acceptance_rate": round(a/max(a+r,1),2)})
    return {"total_feedback": sum(data.get("counts", {}).values()), "meals": sorted(meals, key=lambda x: x["accepted"], reverse=True)}
