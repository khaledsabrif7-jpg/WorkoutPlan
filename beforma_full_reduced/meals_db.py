"""Compact generated meal database for BeForma.

The old project used a very large static meal DB. This version keeps the same
recommendation algorithm but generates a smaller practical database from the
food catalog: 24 breakfast, 60 lunch/dinner bowls and 28 snacks.
"""
from __future__ import annotations
from typing import TypedDict
from foods_catalog import get_food_by_id


class FoodItem(TypedDict):
    food_name: str
    quantity_g: float


class MealRecord(TypedDict):
    name: str
    meal_type: str
    calories: float
    protein: float
    carbs: float
    fat: float
    protein_source: str
    dietary_tags: list[str]
    items: list[FoodItem]
    image: str


def _nutrition(food_id: str, quantity_g: float) -> dict:
    food = get_food_by_id(food_id)
    if not food:
        raise KeyError(food_id)
    factor = quantity_g / 50
    return {
        "id": food_id,
        "name": food["name_en"],
        "category": food["category"],
        "image": food["image"],
        "source": food.get("protein_source"),
        "tags": set(food.get("dietary_tags", [])),
        "calories": food["calories_per_50g"] * factor,
        "protein": food["protein_per_50g"] * factor,
        "carbs": food["carbs_per_50g"] * factor,
        "fat": food["fat_per_50g"] * factor,
        "quantity_g": quantity_g,
    }


def _tags(parts: list[dict], meal_type: str, calories: float, protein: float) -> list[str]:
    cats = {p["category"] for p in parts}
    tag_sets = [p["tags"] for p in parts]
    tags = {meal_type}
    if all("vegan" in t for t in tag_sets) and not cats & {"red_meat", "white_meat", "fish_seafood", "dairy", "eggs"}:
        tags.add("vegan")
    if not cats & {"red_meat", "white_meat", "fish_seafood"}:
        tags.add("vegetarian")
    if not cats & {"red_meat", "white_meat"}:
        tags.add("pescatarian")
    if all("dairy_free" in t for t in tag_sets):
        tags.add("dairy_free")
    if all("gluten_free" in t for t in tag_sets):
        tags.add("gluten_free")
    if protein >= 25 or protein * 4 / max(calories, 1) >= 0.28:
        tags.add("high_protein")
    if calories >= 650:
        tags.add("bulking")
    if calories <= 450 and protein >= 18:
        tags.add("cutting")
    return sorted(tags)


def _make_meal(name: str, meal_type: str, items: list[tuple[str, float]]) -> MealRecord:
    parts = [_nutrition(food_id, qty) for food_id, qty in items]
    calories = round(sum(p["calories"] for p in parts), 1)
    protein = round(sum(p["protein"] for p in parts), 1)
    carbs = round(sum(p["carbs"] for p in parts), 1)
    fat = round(sum(p["fat"] for p in parts), 1)
    protein_source = next((p["source"] for p in parts if p.get("source")), "mixed") or "mixed"
    return {
        "name": name,
        "meal_type": meal_type,
        "calories": calories,
        "protein": protein,
        "carbs": carbs,
        "fat": fat,
        "protein_source": protein_source,
        "dietary_tags": _tags(parts, meal_type, calories, protein),
        "items": [{"food_name": p["name"], "quantity_g": p["quantity_g"]} for p in parts],
        "image": next((p["image"] for p in parts if p.get("source")), parts[0]["image"]),
    }


def _build() -> list[MealRecord]:
    meals: list[MealRecord] = []
    breakfasts = [
        ("Greek Yogurt Oats Bowl", [("greek_yogurt", 200), ("oats", 50), ("berries", 100)]),
        ("Cottage Cheese Banana Bowl", [("cottage_cheese", 200), ("banana", 100), ("almonds", 20)]),
        ("Eggs Whole Grain Breakfast", [("egg_whole", 100), ("whole_grain_bread", 80), ("tomato", 80), ("spinach", 60)]),
        ("Egg White Potato Plate", [("egg_whites", 200), ("potato_boiled", 200), ("spinach", 60)]),
        ("Tofu Oats Breakfast", [("tofu_firm", 150), ("oats", 50), ("berries", 100)]),
        ("Lentil Bread Breakfast", [("lentils_cooked", 180), ("whole_grain_bread", 70), ("tomato", 80)]),
        ("Peanut Butter Banana Oats", [("oats", 60), ("peanut_butter", 25), ("banana", 100)]),
        ("Greek Yogurt Dates Bowl", [("greek_yogurt", 180), ("dates", 50), ("chia_seeds", 15)]),
    ]
    for idx, (name, items) in enumerate(breakfasts, 1):
        meals.append(_make_meal(name, "breakfast", items))
        boosted = items + [("almonds", 15)] if idx % 2 == 0 else items + [("berries", 80)]
        meals.append(_make_meal(f"{name} Plus", "breakfast", boosted))
        light = [(fid, max(50, qty * 0.75)) for fid, qty in items]
        meals.append(_make_meal(f"Light {name}", "breakfast", light))

    proteins = [
        ("Chicken", "chicken_breast_cooked"), ("Turkey", "turkey_breast_cooked"), ("Lean Beef", "lean_beef_cooked"),
        ("Tuna", "tuna_canned_water"), ("Salmon", "salmon_cooked"), ("Shrimp", "shrimp_cooked"),
        ("Tofu", "tofu_firm"), ("Lentils", "lentils_cooked"), ("Chickpeas", "chickpeas_cooked"), ("Black Beans", "black_beans_cooked"),
    ]
    carbs = [("Rice", "rice_white_cooked"), ("Brown Rice", "brown_rice_cooked"), ("Basmati Rice", "basmati_rice_cooked"), ("Potato", "potato_boiled"), ("Sweet Potato", "sweet_potato"), ("Quinoa", "quinoa_cooked"), ("Pasta", "whole_wheat_pasta_cooked")]
    vegs = ["broccoli", "spinach", "green_beans", "zucchini", "cauliflower", "bell_pepper"]
    for i, (pname, pid) in enumerate(proteins):
        for j, (cname, cid) in enumerate(carbs[:3]):
            veg = vegs[(i + j) % len(vegs)]
            meals.append(_make_meal(f"{pname} {cname} Lunch Bowl", "lunch", [(pid, 170 if 'Beans' not in pname and pname != 'Lentils' else 220), (cid, 180), (veg, 140), ("olive_oil", 10)]))
        for j, (cname, cid) in enumerate(carbs[3:6]):
            veg = vegs[(i + j + 2) % len(vegs)]
            meals.append(_make_meal(f"{pname} {cname} Dinner Plate", "dinner", [(pid, 160 if 'Beans' not in pname and pname != 'Lentils' else 210), (cid, 190), (veg, 160), ("avocado", 50)]))

    snacks = [
        ("Greek Yogurt Berry Snack", [("greek_yogurt", 200), ("berries", 100)]),
        ("Cottage Cheese Fruit Snack", [("cottage_cheese", 180), ("apple", 100)]),
        ("Banana Peanut Butter Snack", [("banana", 100), ("peanut_butter", 25)]),
        ("Dates Almonds Snack", [("dates", 50), ("almonds", 25)]),
        ("Hummus Rice Cakes Snack", [("hummus", 80), ("rice_cakes", 50)]),
        ("Protein Bar Snack", [("protein_bar", 50), ("orange", 100)]),
        ("Trail Mix Snack", [("trail_mix", 50), ("milk_low_fat", 200)]),
        ("Egg White Snack", [("egg_whites", 150), ("rice_cakes", 50)]),
        ("Tofu Avocado Snack", [("tofu_firm", 120), ("avocado", 50)]),
        ("Popcorn Fruit Snack", [("air_popped_popcorn", 50), ("grapes", 100)]),
        ("Chia Yogurt Snack", [("greek_yogurt", 170), ("chia_seeds", 15), ("berries", 80)]),
        ("Dark Chocolate Nuts Snack", [("dark_chocolate", 25), ("walnuts", 20)]),
        ("High Calorie Oats Snack", [("oats", 50), ("peanut_butter", 25), ("banana", 100)]),
        ("Vegan Chickpea Snack", [("chickpeas_cooked", 120), ("cucumber", 100), ("tomato", 100)]),
    ]
    for name, items in snacks:
        meals.append(_make_meal(name, "snack", items))
        meals.append(_make_meal(f"Large {name}", "snack", items + [("almonds", 15)]))
    return meals


MEALS_DB: list[MealRecord] = _build()


def count_by_type() -> dict[str, int]:
    counts: dict[str, int] = {}
    for meal in MEALS_DB:
        counts[meal["meal_type"]] = counts.get(meal["meal_type"], 0) + 1
    return counts
