"""Nutrition target calculation using Mifflin-St Jeor BMR -> TDEE -> goal-adjusted calories/macros."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class NutritionPlan:
    daily_calories: float
    protein_grams: float
    carbs_grams: float
    fat_grams: float
    bmr: float
    tdee: float
    goal: str

    def as_dict(self) -> dict:
        return {
            "daily_calories": round(self.daily_calories),
            "protein_grams": round(self.protein_grams),
            "carbs_grams": round(self.carbs_grams),
            "fat_grams": round(self.fat_grams),
            "bmr": round(self.bmr),
            "tdee": round(self.tdee),
            "goal": self.goal,
        }


GOAL_ADJUSTMENTS = {"lose": -500, "maintain": 0, "gain": 300}

GOAL_MACRO_RATIOS = {
    "lose": {"protein": 0.40, "carbs": 0.35, "fat": 0.25},
    "maintain": {"protein": 0.30, "carbs": 0.40, "fat": 0.30},
    "gain": {"protein": 0.30, "carbs": 0.50, "fat": 0.20},
}


def normalize_goal(goal: str) -> str:
    value = (goal or "maintain").strip().lower().replace("-", "_").replace(" ", "_")
    mapping = {
        "lose": "lose", "loss": "lose", "weight_loss": "lose", "fat_loss": "lose", "cut": "lose", "cutting": "lose",
        "maintain": "maintain", "maintenance": "maintain", "stable": "maintain",
        "gain": "gain", "muscle_gain": "gain", "bulk": "gain", "bulking": "gain", "build_muscle": "gain",
    }
    return mapping.get(value, "maintain")


def activity_factor(activity_level: str | float | int) -> float:
    if isinstance(activity_level, (int, float)):
        return max(1.0, min(float(activity_level), 2.2))
    value = (activity_level or "sedentary").strip().lower().replace("_", " ").replace("-", " ")
    mapping = {
        "sedentary": 1.2,
        "light": 1.375,
        "lightly active": 1.375,
        "moderate": 1.55,
        "moderately active": 1.55,
        "active": 1.725,
        "very active": 1.725,
        "super active": 1.9,
        "athlete": 1.9,
    }
    return mapping.get(value, 1.2)


def generate_nutrition_plan(age: int, gender: str, height: float, weight: float, activity_level: float, goal: str) -> NutritionPlan:
    goal = normalize_goal(goal)
    gender_norm = (gender or "male").lower().strip()
    if gender_norm in {"female", "f"}:
        bmr = 10 * weight + 6.25 * height - 5 * age - 161
    elif gender_norm in {"male", "m"}:
        bmr = 10 * weight + 6.25 * height - 5 * age + 5
    else:
        bmr = 10 * weight + 6.25 * height - 5 * age - 78
    tdee = bmr * float(activity_level)
    daily_calories = max(1200, tdee + GOAL_ADJUSTMENTS[goal])
    ratios = GOAL_MACRO_RATIOS[goal]
    return NutritionPlan(
        daily_calories=daily_calories,
        protein_grams=(daily_calories * ratios["protein"]) / 4,
        carbs_grams=(daily_calories * ratios["carbs"]) / 4,
        fat_grams=(daily_calories * ratios["fat"]) / 9,
        bmr=bmr,
        tdee=tdee,
        goal=goal,
    )


def calculate_bmi(height_cm: float, weight_kg: float) -> tuple[float, str]:
    bmi = weight_kg / ((height_cm / 100) ** 2)
    if bmi < 18.5:
        category = "underweight"
    elif bmi < 25:
        category = "normal"
    elif bmi < 30:
        category = "overweight"
    else:
        category = "obese"
    return round(bmi, 2), category
