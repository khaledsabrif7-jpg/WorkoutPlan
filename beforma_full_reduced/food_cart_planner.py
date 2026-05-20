"""Food-cart based meal recommendation mode.

The cart capacity is the user's daily calorie target. Users add foods in 50g
steps, and the system auto-fills missing calories/macros when needed.
"""
from __future__ import annotations
from fastapi import HTTPException

from foods_catalog import FOOD_CATALOG, FoodRecord, food_allowed, get_food_by_id
from meal_selector import MEAL_CALORIE_SHARE_BY_COUNT, MEAL_TYPE_PLANS
from nutrition import NutritionPlan
from optimizer import MacroTarget, optimize_meal_plan
from validator import validate_plan


def calculate_food_nutrition(food: FoodRecord, quantity_g: float, source: str = "user_selected") -> dict:
    factor = quantity_g / 50
    return {
        "food_id": food["id"],
        "food_name_en": food["name_en"],
        "food_name_ar": food["name_ar"],
        "quantity_g": float(quantity_g),
        "calories": round(food["calories_per_50g"] * factor, 1),
        "protein": round(food["protein_per_50g"] * factor, 1),
        "carbs": round(food["carbs_per_50g"] * factor, 1),
        "fat": round(food["fat_per_50g"] * factor, 1),
        "category": food["category"],
        "image": food["image"],
        "protein_source": food.get("protein_source"),
        "compatible_meal_types": food.get("compatible_meal_types", ["lunch", "dinner"]),
        "dietary_tags": food.get("dietary_tags", []),
        "source": source,
    }


def _selected_to_entries(selected_foods: list[dict]) -> list[dict]:
    entries = []
    for item in selected_foods:
        food_id = item.get("food_id")
        qty = float(item.get("quantity_g", 0))
        food = get_food_by_id(food_id)
        if not food:
            raise HTTPException(status_code=404, detail={"error": "FOOD_NOT_FOUND", "food_id": food_id})
        if qty < 50 or qty % 50 != 0:
            raise HTTPException(status_code=422, detail={"error": "INVALID_QUANTITY", "food_id": food_id, "message": "quantity_g must be a multiple of 50 and at least 50g."})
        entries.append(calculate_food_nutrition(food, qty, "user_selected"))
    return entries


def calculate_cart_totals(selected_foods: list[dict]) -> dict:
    entries = _selected_to_entries(selected_foods)
    return _totals(entries) | {"selected_items": entries}


def _totals(entries: list[dict]) -> dict:
    return {
        "calories": round(sum(x["calories"] for x in entries), 1),
        "protein": round(sum(x["protein"] for x in entries), 1),
        "carbs": round(sum(x["carbs"] for x in entries), 1),
        "fat": round(sum(x["fat"] for x in entries), 1),
    }


def validate_cart(selected_foods: list[dict], nutrition_plan: NutritionPlan, dietary_preference: str | None, allow_overflow: bool = False) -> dict:
    entries = _selected_to_entries(selected_foods)
    for entry in entries:
        food = get_food_by_id(entry["food_id"])
        if food and not food_allowed(food, dietary_preference):
            raise HTTPException(status_code=422, detail={
                "error": "DIETARY_CONFLICT",
                "food_id": entry["food_id"],
                "food_name": entry["food_name_en"],
                "dietaryPreference": dietary_preference or "normal",
                "message": "This food is not allowed for the selected dietary preference.",
            })
    totals = _totals(entries)
    target = nutrition_plan.daily_calories
    if totals["calories"] > target * 1.05 and not allow_overflow:
        raise HTTPException(status_code=422, detail={
            "error": "CART_OVERFLOW",
            "target_calories": round(target, 1),
            "selected_calories": totals["calories"],
            "overflow_calories": round(totals["calories"] - target, 1),
            "message": "Cart exceeds daily calorie target.",
        })
    return {"entries": entries, "totals": totals}


def _macro_error(totals: dict, target: dict) -> float:
    return (
        abs(totals["calories"] - target["calories"]) / max(target["calories"], 1)
        + 2.2 * abs(totals["protein"] - target["protein"]) / max(target["protein"], 1)
        + abs(totals["carbs"] - target["carbs"]) / max(target["carbs"], 1)
        + abs(totals["fat"] - target["fat"]) / max(target["fat"], 1)
    ) / 5.2


def _candidate_pool(dietary_preference: str | None, goal: str, current: dict, target: dict) -> list[FoodRecord]:
    protein_low = current["protein"] < target["protein"] * 0.92
    carbs_low = current["carbs"] < target["carbs"] * 0.92
    fat_low = current["fat"] < target["fat"] * 0.90
    preferred_ids: set[str] = set()
    if protein_low:
        preferred_ids |= {"chicken_breast_cooked", "turkey_breast_cooked", "tuna_canned_water", "shrimp_cooked", "greek_yogurt", "egg_whites", "tofu_firm", "lentils_cooked"}
    if carbs_low:
        preferred_ids |= {"rice_white_cooked", "brown_rice_cooked", "oats", "potato_boiled", "sweet_potato", "quinoa_cooked", "banana", "dates"}
    if fat_low:
        preferred_ids |= {"olive_oil", "avocado", "almonds", "walnuts", "peanut_butter", "salmon_cooked"}
    if goal == "lose":
        preferred_ids |= {"broccoli", "spinach", "cucumber", "tomato", "chicken_breast_cooked", "tuna_canned_water", "egg_whites"}
    if goal == "gain":
        preferred_ids |= {"oats", "dates", "peanut_butter", "rice_white_cooked", "salmon_cooked", "protein_bar", "trail_mix"}

    pool = [f for f in FOOD_CATALOG if food_allowed(f, dietary_preference)]
    pool.sort(key=lambda f: (f["id"] not in preferred_ids, -f["protein_per_50g"], f["calories_per_50g"]))
    return pool[:45]


def autofill_remaining_foods(selected_entries: list[dict], nutrition_plan: NutritionPlan, dietary_preference: str | None, goal: str) -> tuple[list[dict], list[dict]]:
    target = {
        "calories": nutrition_plan.daily_calories,
        "protein": nutrition_plan.protein_grams,
        "carbs": nutrition_plan.carbs_grams,
        "fat": nutrition_plan.fat_grams,
    }
    entries = list(selected_entries)
    auto: list[dict] = []
    used_steps: dict[str, int] = {}
    for _ in range(60):
        totals = _totals(entries)
        if target["calories"] * 0.95 <= totals["calories"] <= target["calories"] * 1.03 and _macro_error(totals, target) < 0.18:
            break
        if totals["calories"] >= target["calories"] * 1.03:
            break
        best = None
        best_score = float("inf")
        for food in _candidate_pool(dietary_preference, goal, totals, target):
            if used_steps.get(food["id"], 0) >= 5:
                continue
            cand = calculate_food_nutrition(food, 50, "auto_filled")
            new_totals = _totals(entries + [cand])
            if new_totals["calories"] > target["calories"] * 1.06:
                continue
            diversity_penalty = used_steps.get(food["id"], 0) * 0.025
            score = _macro_error(new_totals, target) + diversity_penalty
            if score < best_score:
                best_score = score
                best = cand
        if not best:
            break
        entries.append(best)
        auto.append(best)
        used_steps[best["food_id"]] = used_steps.get(best["food_id"], 0) + 1
    return entries, auto


def _meal_name(items: list[dict], meal_type: str) -> str:
    ids = {x["food_id"] for x in items}
    if {"chicken_breast_cooked", "rice_white_cooked"} <= ids or {"chicken_breast_cooked", "brown_rice_cooked"} <= ids:
        return "Chicken Rice Bowl"
    if "salmon_cooked" in ids and ("potato_boiled" in ids or "sweet_potato" in ids):
        return "Salmon Potato Plate"
    if "greek_yogurt" in ids and "oats" in ids:
        return "Greek Yogurt Oats Bowl"
    if "lentils_cooked" in ids and any(x in ids for x in ["rice_white_cooked", "brown_rice_cooked", "basmati_rice_cooked"]):
        return "Lentil Rice Bowl"
    if "egg_whites" in ids or "egg_whole" in ids:
        return "Egg Breakfast Plate" if meal_type == "breakfast" else "Egg Protein Plate"
    if "lean_beef_cooked" in ids and "whole_wheat_pasta_cooked" in ids:
        return "Beef Pasta Bowl"
    if "tuna_canned_water" in ids and any(x in ids for x in ["rice_white_cooked", "brown_rice_cooked"]):
        return "Tuna Rice Bowl"
    if "tofu_firm" in ids and "quinoa_cooked" in ids:
        return "Tofu Quinoa Bowl"
    if meal_type == "snack":
        return "Smart Snack Bowl"
    return f"Custom {meal_type.title()} Plate"


def build_meals_from_food_cart(final_foods: list[dict], nutrition_plan: NutritionPlan, num_meals: int, goal: str, dietary_preference: str | None) -> list[dict]:
    num_meals = 5 if num_meals >= 5 else 4 if num_meals == 4 else 3
    slots = MEAL_TYPE_PLANS[num_meals]
    shares = MEAL_CALORIE_SHARE_BY_COUNT[num_meals]
    buckets = [[] for _ in slots]
    bucket_cal = [0.0 for _ in slots]
    target_cals = [nutrition_plan.daily_calories * share for share in shares]

    # Larger protein/starch items first so meals become more complete.
    ordered = sorted(final_foods, key=lambda x: (x["category"] in {"vegetables", "fruits", "herbs_sauces"}, -x["calories"]))
    for item in ordered:
        compatible = set(item.get("compatible_meal_types", []))
        choices = [i for i, slot in enumerate(slots) if slot in compatible] or list(range(len(slots)))
        idx = min(choices, key=lambda i: bucket_cal[i] / max(target_cals[i], 1))
        buckets[idx].append(item)
        bucket_cal[idx] += item["calories"]

    meals: list[dict] = []
    for slot, items in zip(slots, buckets):
        if not items:
            continue
        totals = _totals(items)
        protein_source = next((x.get("protein_source") for x in items if x.get("protein_source")), "mixed") or "mixed"
        image = next((x["image"] for x in items if x.get("protein_source")), items[0]["image"])
        cats = sorted({x["category"] for x in items})
        meals.append({
            "name": _meal_name(items, slot),
            "meal_type": slot,
            "calories": totals["calories"],
            "protein": totals["protein"],
            "carbs": totals["carbs"],
            "fat": totals["fat"],
            "protein_source": protein_source,
            "items": [
                {"food_id": x["food_id"], "food_name_en": x["food_name_en"], "food_name_ar": x["food_name_ar"], "quantity_g": x["quantity_g"], "source": x["source"]}
                for x in items
            ],
            "image": image,
            "tags": [slot, goal, dietary_preference or "normal"] + cats,
        })
    return meals


def _validation_dict(validation) -> dict:
    return {"passed": validation.passed, "score": validation.score, "issues": [{"severity": i.severity, "code": i.code, "message": i.message, "detail": i.detail} for i in validation.issues]}


def generate_cart_based_plan(nutrition_plan: NutritionPlan, selected_foods: list[dict], num_meals: int, goal: str, dietary_preference: str | None, auto_fill_remaining: bool = True, allow_overflow: bool = False) -> dict:
    checked = validate_cart(selected_foods, nutrition_plan, dietary_preference, allow_overflow)
    selected_entries = checked["entries"]
    before_totals = checked["totals"]
    if not selected_entries:
        return {"fallback_to_ai": True}

    auto_entries: list[dict] = []
    final_entries = selected_entries
    if auto_fill_remaining and before_totals["calories"] < nutrition_plan.daily_calories * 0.95:
        final_entries, auto_entries = autofill_remaining_foods(selected_entries, nutrition_plan, dietary_preference, goal)

    meals = build_meals_from_food_cart(final_entries, nutrition_plan, num_meals, goal, dietary_preference)
    target = MacroTarget(nutrition_plan.daily_calories, nutrition_plan.protein_grams, nutrition_plan.carbs_grams, nutrition_plan.fat_grams)
    optimized = optimize_meal_plan(meals, target, strategy="flexible")
    validation = validate_plan(optimized.meals, optimized.plan_totals, nutrition_plan.daily_calories, nutrition_plan.goal, calorie_tolerance=0.08)
    selected_categories = sorted({x["category"] for x in selected_entries})
    return {
        "daily_targets": nutrition_plan.as_dict(),
        "daily_plan_totals": optimized.plan_totals,
        "meals": optimized.meals,
        "strategy": "user_cart_auto_fill" if auto_entries else "user_cart_only",
        "optimized": optimized.converged,
        "quality_score": validation.score,
        "accuracy": {
            "macro_error_pct": optimized.error_pct,
            "validation_score": validation.score,
            "note": "This is macro-matching accuracy, not medical accuracy.",
        },
        "validation": _validation_dict(validation),
        "food_selection": {
            "mode": "user_cart",
            "cart_total_calories": before_totals["calories"],
            "target_calories": round(nutrition_plan.daily_calories, 1),
            "remaining_before_autofill": round(nutrition_plan.daily_calories - before_totals["calories"], 1),
            "auto_fill_used": bool(auto_entries),
            "user_selected_foods_count": len(selected_entries),
            "auto_filled_foods_count": len(auto_entries),
            "selected_categories": selected_categories,
        },
    }


def preview_cart(selected_foods: list[dict], nutrition_plan: NutritionPlan, dietary_preference: str | None) -> dict:
    checked = validate_cart(selected_foods, nutrition_plan, dietary_preference, allow_overflow=True)
    totals = checked["totals"]
    remaining = {
        "calories": round(nutrition_plan.daily_calories - totals["calories"], 1),
        "protein": round(nutrition_plan.protein_grams - totals["protein"], 1),
        "carbs": round(nutrition_plan.carbs_grams - totals["carbs"], 1),
        "fat": round(nutrition_plan.fat_grams - totals["fat"], 1),
    }
    progress = round((totals["calories"] / max(nutrition_plan.daily_calories, 1)) * 100, 1)
    if totals["calories"] == 0:
        status = "empty"
    elif totals["calories"] > nutrition_plan.daily_calories * 1.05:
        status = "over_target"
    elif totals["calories"] >= nutrition_plan.daily_calories * 0.95:
        status = "complete"
    else:
        status = "under_target"
    warnings = []
    if status == "over_target":
        warnings.append("Cart exceeds daily calorie target.")
    if status == "under_target":
        warnings.append("Cart is under target; auto-fill can complete the missing calories/macros.")
    return {
        "daily_calorie_target": round(nutrition_plan.daily_calories),
        "macros_target": {
            "protein_grams": round(nutrition_plan.protein_grams),
            "carbs_grams": round(nutrition_plan.carbs_grams),
            "fat_grams": round(nutrition_plan.fat_grams),
        },
        "cart_totals": totals,
        "remaining": remaining,
        "progress_pct": progress,
        "status": status,
        "warnings": warnings,
        "selected_items": checked["entries"],
    }
