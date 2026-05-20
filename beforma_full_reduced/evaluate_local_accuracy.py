"""Evaluate BeForma compact project quality locally.

Run:
    python evaluate_local_accuracy.py
"""
from __future__ import annotations
import csv
import time
from statistics import mean

from main import GeneratePlanRequest, generate_plan
from workout_generator import generate_workout_plan


def pct_accuracy(actual: float, target: float) -> float:
    return max(0.0, 100.0 - abs(actual - target) / max(target, 1) * 100.0)


NUTRITION_CASES = [
    {"label":"AI Lose Beginner", "age":24,"gender":"male","height":178,"weight":82,"fitnessGoal":"lose","activityLevel":"Sedentary","experienceLevel":"Beginner","workoutLocation":"Home","dietaryPreference":"normal"},
    {"label":"AI Maintain Gym", "age":26,"gender":"male","height":176,"weight":73,"fitnessGoal":"maintain","activityLevel":"Moderately Active","experienceLevel":"Intermediate","workoutLocation":"Gym","dietaryPreference":"normal"},
    {"label":"AI Gain Gym", "age":25,"gender":"male","height":178,"weight":72,"fitnessGoal":"gain","activityLevel":"Moderately Active","experienceLevel":"Intermediate","workoutLocation":"Gym","dietaryPreference":"normal"},
    {"label":"AI Vegan Lose", "age":31,"gender":"female","height":160,"weight":70,"fitnessGoal":"lose","activityLevel":"Sedentary","experienceLevel":"Beginner","workoutLocation":"Home","dietaryPreference":"vegan"},
    {"label":"AI Pescatarian Gain", "age":33,"gender":"female","height":166,"weight":59,"fitnessGoal":"muscle_gain","activityLevel":"Moderately Active","experienceLevel":"Intermediate","workoutLocation":"Gym","dietaryPreference":"pescatarian"},
]

CART_CASES = [
    {"label":"Cart Underfilled AutoFill", "age":24,"gender":"male","height":178,"weight":82,"fitnessGoal":"gain","activityLevel":"Moderately Active","experienceLevel":"Intermediate","workoutLocation":"Gym","dietaryPreference":"normal","selectionMode":"user_cart","selectedFoods":[{"food_id":"chicken_breast_cooked","quantity_g":200},{"food_id":"rice_white_cooked","quantity_g":250},{"food_id":"banana","quantity_g":100}]},
    {"label":"Cart Vegan", "age":27,"gender":"female","height":165,"weight":62,"fitnessGoal":"maintain","activityLevel":"Lightly Active","experienceLevel":"Beginner","workoutLocation":"Home","dietaryPreference":"vegan","selectionMode":"user_cart","selectedFoods":[{"food_id":"tofu_firm","quantity_g":200},{"food_id":"brown_rice_cooked","quantity_g":250},{"food_id":"broccoli","quantity_g":150}]},
    {"label":"Cart Pescatarian", "age":30,"gender":"male","height":180,"weight":78,"fitnessGoal":"lose","activityLevel":"Moderately Active","experienceLevel":"Intermediate","workoutLocation":"Gym","dietaryPreference":"pescatarian","selectionMode":"user_cart","selectedFoods":[{"food_id":"salmon_cooked","quantity_g":200},{"food_id":"potato_boiled","quantity_g":250},{"food_id":"spinach","quantity_g":100}]},
    {"label":"Cart Empty Fallback", "age":22,"gender":"male","height":175,"weight":66,"fitnessGoal":"gain","activityLevel":"Lightly Active","experienceLevel":"Beginner","workoutLocation":"Home","dietaryPreference":"normal","selectionMode":"user_cart","selectedFoods":[]},
]

WORKOUT_CASES = [
    {"label":"Workout Home Lose", "fitnessGoal":"lose", "experienceLevel":"Beginner", "workoutLocation":"Home"},
    {"label":"Workout Gym Gain", "fitnessGoal":"gain", "experienceLevel":"Intermediate", "workoutLocation":"Gym"},
    {"label":"Workout Advanced Gym", "fitnessGoal":"bulk", "experienceLevel":"Advanced", "workoutLocation":"Gym"},
]


def evaluate_plan(case: dict) -> dict:
    label = case.pop("label")
    start = time.perf_counter()
    response = generate_plan(GeneratePlanRequest(**case))
    elapsed_ms = (time.perf_counter() - start) * 1000
    target_cal = response["daily_calorie_target"]
    meals = response["recommendations"]["diet_plan"]
    totals = {
        "calories": sum(m["calories"] for m in meals),
        "protein_grams": sum(m["protein"] for m in meals),
        "carbs_grams": sum(m["carbs"] for m in meals),
        "fat_grams": sum(m["fat"] for m in meals),
    }
    macros = response["macros"]
    macro_acc = mean([
        pct_accuracy(totals["protein_grams"], macros["protein_grams"]),
        pct_accuracy(totals["carbs_grams"], macros["carbs_grams"]),
        pct_accuracy(totals["fat_grams"], macros["fat_grams"]),
    ])
    return {
        "label": label,
        "type": "nutrition",
        "passed": response["plan_quality"]["validation"]["passed"],
        "calorie_accuracy": round(pct_accuracy(totals["calories"], target_cal), 2),
        "macro_accuracy": round(macro_acc, 2),
        "meal_image_coverage": round(sum(1 for m in meals if m.get("image")) / max(len(meals), 1) * 100, 2),
        "exercise_image_coverage": "",
        "quality_score": response["plan_quality"]["quality_score"],
        "elapsed_ms": round(elapsed_ms, 1),
    }


def evaluate_workout(case: dict) -> dict:
    label = case.pop("label")
    start = time.perf_counter()
    plan = generate_workout_plan(case["fitnessGoal"], case["experienceLevel"], case["workoutLocation"])
    elapsed_ms = (time.perf_counter() - start) * 1000
    exercises = [ex for day in plan["weekly_plan"] for ex in day["exercises"]]
    image_cov = sum(1 for ex in exercises if ex.get("image")) / max(len(exercises), 1) * 100
    return {
        "label": label,
        "type": "workout",
        "passed": bool(plan["weekly_plan"]) and image_cov == 100,
        "calorie_accuracy": "",
        "macro_accuracy": "",
        "meal_image_coverage": "",
        "exercise_image_coverage": round(image_cov, 2),
        "quality_score": 100 if image_cov == 100 else 70,
        "elapsed_ms": round(elapsed_ms, 1),
    }


def main() -> None:
    rows = []
    for case in NUTRITION_CASES + CART_CASES:
        rows.append(evaluate_plan(dict(case)))
    for case in WORKOUT_CASES:
        rows.append(evaluate_workout(dict(case)))

    with open("accuracy_report.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)

    nutrition = [r for r in rows if r["type"] == "nutrition"]
    workouts = [r for r in rows if r["type"] == "workout"]
    summary = {
        "test_cases": len(rows),
        "validation_pass_rate": f"{sum(1 for r in rows if r['passed'])}/{len(rows)}",
        "avg_calorie_accuracy": round(mean(float(r["calorie_accuracy"]) for r in nutrition), 2),
        "avg_macro_accuracy": round(mean(float(r["macro_accuracy"]) for r in nutrition), 2),
        "meal_image_coverage": round(mean(float(r["meal_image_coverage"]) for r in nutrition), 2),
        "exercise_image_coverage": round(mean(float(r["exercise_image_coverage"]) for r in workouts), 2),
        "avg_response_time_ms": round(mean(float(r["elapsed_ms"]) for r in rows), 1),
        "client_usefulness_score": round(mean(float(r["quality_score"]) for r in rows), 2),
    }
    summary["verdict"] = "EXCELLENT" if summary["client_usefulness_score"] >= 90 else "GOOD" if summary["client_usefulness_score"] >= 75 else "NEEDS_IMPROVEMENT"
    print(summary)


if __name__ == "__main__":
    main()
