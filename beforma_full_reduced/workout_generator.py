"""Workout generation based on goal, experience and location."""
from __future__ import annotations
from nutrition import normalize_goal
from exercises_db import EXERCISES_DB


DIFFICULTY_ORDER = {"beginner": 1, "intermediate": 2, "advanced": 3}


def _norm_level(level: str | None) -> str:
    value = (level or "beginner").strip().lower()
    if value in {"advanced", "pro"}:
        return "advanced"
    if value in {"intermediate", "medium"}:
        return "intermediate"
    return "beginner"


def _allowed(ex: dict, location: str, level: str, goal: str) -> bool:
    if location not in [x.lower() for x in ex["location"]]:
        return False
    if DIFFICULTY_ORDER[ex["difficulty"]] > DIFFICULTY_ORDER[level] + 1:
        return False
    if goal not in ex["goal_tags"]:
        return False
    return True


def _exercise_payload(ex: dict, level: str) -> dict:
    defaults = ex["sets_reps_default"].get(level) or ex["sets_reps_default"]["beginner"]
    return {
        "exercise_id": ex["id"],
        "name_en": ex["name_en"],
        "name_ar": ex["name_ar"],
        "image": ex["image"],
        "sets": defaults["sets"],
        "reps": defaults["reps"],
        "rest_seconds": defaults["rest_seconds"],
        "primary_muscles": ex["primary_muscles"],
        "equipment": ex["equipment"],
        "instructions": ex["instructions"],
    }


def generate_workout_plan(fitness_goal: str, experience_level: str, workout_location: str, days_per_week: int | None = None) -> dict:
    goal = normalize_goal(fitness_goal)
    level = _norm_level(experience_level)
    location = "gym" if "gym" in (workout_location or "home").lower() else "home"
    default_days = 3 if level == "beginner" else 4 if level == "intermediate" else 5
    days = max(2, min(days_per_week or default_days, 6))

    if goal == "gain":
        focus = "progressive overload and hypertrophy"
        cardio = "10-15 min light cardio after lifting"
    elif goal == "lose":
        focus = "strength training with calorie-burning circuits"
        cardio = "20-30 min moderate cardio 3x/week"
    else:
        focus = "balanced strength and fitness maintenance"
        cardio = "15-20 min cardio 2x/week"

    pool = [e for e in EXERCISES_DB if _allowed(e, location, level, goal)]
    strength = [e for e in pool if e["category"] == "strength"]
    cardio_ex = [e for e in pool if e["category"] == "cardio"]
    core = [e for e in pool if e["category"] == "core"]
    mobility = [e for e in pool if e["category"] == "mobility"]

    weekly = []
    for day in range(1, days + 1):
        exercises = []
        start = (day - 1) * 3
        exercises.extend(strength[start % max(len(strength), 1): start % max(len(strength), 1) + 4])
        if len(exercises) < 4:
            exercises.extend(strength[: 4 - len(exercises)])
        if goal == "lose" and cardio_ex:
            exercises.append(cardio_ex[(day - 1) % len(cardio_ex)])
        elif goal == "gain" and core:
            exercises.append(core[(day - 1) % len(core)])
        elif cardio_ex:
            exercises.append(cardio_ex[(day - 1) % len(cardio_ex)])
        if mobility:
            exercises.append(mobility[(day - 1) % len(mobility)])
        # de-duplicate while preserving order
        seen = set(); unique = []
        for ex in exercises:
            if ex["id"] not in seen:
                seen.add(ex["id"]); unique.append(ex)
        weekly.append({
            "day": day,
            "title": "Full Body Strength" if location == "home" else ("Upper/Lower Gym Session" if day % 2 else "Lower/Push Gym Session"),
            "estimated_duration_minutes": 35 if level == "beginner" else 45 if level == "intermediate" else 60,
            "exercises": [_exercise_payload(ex, level) for ex in unique[:6]],
        })

    return {
        "fitnessGoal": fitness_goal,
        "normalizedGoal": goal,
        "experienceLevel": experience_level,
        "workoutLocation": workout_location,
        "days_per_week": days,
        "focus": focus,
        "cardio": cardio,
        "progression_note": "Increase reps or weight gradually when all sets feel easy." if goal == "gain" else "Keep movement quality high and adjust intensity to recovery.",
        "weekly_plan": weekly,
    }
