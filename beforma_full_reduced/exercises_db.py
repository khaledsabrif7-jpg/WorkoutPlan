"""Exercise database with images for workout generation."""
from __future__ import annotations
from typing import Optional, TypedDict


class ExerciseRecord(TypedDict):
    id: str
    name_en: str
    name_ar: str
    category: str
    primary_muscles: list[str]
    secondary_muscles: list[str]
    equipment: str
    location: list[str]
    difficulty: str
    goal_tags: list[str]
    image: str
    instructions: list[str]
    common_mistakes: list[str]
    sets_reps_default: dict[str, dict]


IMG_STRENGTH = "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?auto=format&fit=crop&w=800&q=80"
IMG_GYM = "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?auto=format&fit=crop&w=800&q=80"
IMG_CARDIO = "https://images.unsplash.com/photo-1552674605-db6ffd4facb5?auto=format&fit=crop&w=800&q=80"
IMG_CORE = "https://images.unsplash.com/photo-1518611012118-696072aa579a?auto=format&fit=crop&w=800&q=80"
IMG_MOBILITY = "https://images.unsplash.com/photo-1506126613408-eca07ce68773?auto=format&fit=crop&w=800&q=80"


def _defaults(difficulty: str = "beginner") -> dict[str, dict]:
    return {
        "beginner": {"sets": 3, "reps": "8-12", "rest_seconds": 60},
        "intermediate": {"sets": 4, "reps": "10-15", "rest_seconds": 60},
        "advanced": {"sets": 5, "reps": "12-20", "rest_seconds": 45},
    }


def _ex(id, en, ar, category, muscles, equipment, location, difficulty="beginner", secondary=None, img=None):
    return {
        "id": id,
        "name_en": en,
        "name_ar": ar,
        "category": category,
        "primary_muscles": muscles,
        "secondary_muscles": secondary or [],
        "equipment": equipment,
        "location": location,
        "difficulty": difficulty,
        "goal_tags": ["lose", "maintain", "gain"],
        "image": img or (IMG_CARDIO if category == "cardio" else IMG_CORE if category == "core" else IMG_MOBILITY if category == "mobility" else IMG_GYM if "gym" in location else IMG_STRENGTH),
        "instructions": [
            f"Set up safely for {en}.",
            "Move with control through the full comfortable range of motion.",
            "Keep breathing steady and stop if you feel sharp pain."
        ],
        "common_mistakes": ["Using momentum", "Rushing reps", "Losing posture"],
        "sets_reps_default": _defaults(difficulty),
    }


EXERCISES_DB: list[ExerciseRecord] = [
    _ex("push_up", "Push-up", "ضغط", "strength", ["chest", "triceps", "shoulders"], "bodyweight", ["home"], secondary=["core"]),
    _ex("incline_push_up", "Incline Push-up", "ضغط مائل", "strength", ["chest", "triceps"], "bodyweight", ["home"], secondary=["shoulders"]),
    _ex("bodyweight_squat", "Bodyweight Squat", "سكوات وزن الجسم", "strength", ["quads", "glutes"], "bodyweight", ["home"], secondary=["core"]),
    _ex("jump_squat", "Jump Squat", "سكوات قفز", "cardio", ["quads", "glutes"], "bodyweight", ["home"], "intermediate", ["calves"], IMG_CARDIO),
    _ex("forward_lunge", "Forward Lunge", "لانجز أمامي", "strength", ["quads", "glutes"], "bodyweight", ["home"], secondary=["hamstrings"]),
    _ex("glute_bridge", "Glute Bridge", "جسر الحوض", "strength", ["glutes", "hamstrings"], "bodyweight", ["home"], secondary=["core"]),
    _ex("plank", "Plank", "بلانك", "core", ["core"], "bodyweight", ["home"], img=IMG_CORE),
    _ex("side_plank", "Side Plank", "بلانك جانبي", "core", ["core"], "bodyweight", ["home"], img=IMG_CORE),
    _ex("mountain_climbers", "Mountain Climbers", "متسلق الجبال", "cardio", ["core", "full_body"], "bodyweight", ["home"], "intermediate", img=IMG_CARDIO),
    _ex("burpee", "Burpee", "بيربي", "cardio", ["full_body"], "bodyweight", ["home"], "advanced", img=IMG_CARDIO),
    _ex("jumping_jacks", "Jumping Jacks", "جامبينج جاكس", "cardio", ["full_body"], "bodyweight", ["home"], img=IMG_CARDIO),
    _ex("high_knees", "High Knees", "رفع الركبة", "cardio", ["full_body", "core"], "bodyweight", ["home"], img=IMG_CARDIO),
    _ex("chair_dips", "Chair Dips", "ديبس كرسي", "strength", ["triceps", "shoulders"], "chair", ["home"], secondary=["chest"]),
    _ex("leg_raise", "Leg Raise", "رفع الرجل", "core", ["core"], "bodyweight", ["home"], img=IMG_CORE),
    _ex("superman", "Superman", "سوبرمان", "strength", ["back", "glutes"], "bodyweight", ["home"]),
    _ex("calf_raise", "Calf Raise", "رفع السمانة", "strength", ["calves"], "bodyweight", ["home", "gym"]),
    _ex("bench_press", "Bench Press", "بنش برس", "strength", ["chest", "triceps"], "barbell", ["gym"], "intermediate", ["shoulders"], IMG_GYM),
    _ex("chest_press_machine", "Chest Press Machine", "ماكينة صدر", "strength", ["chest", "triceps"], "machine", ["gym"], img=IMG_GYM),
    _ex("dumbbell_press", "Dumbbell Press", "ضغط دمبل", "strength", ["chest", "shoulders"], "dumbbells", ["gym"], "intermediate", ["triceps"], IMG_GYM),
    _ex("lat_pulldown", "Lat Pulldown", "سحب عالي", "strength", ["back", "biceps"], "machine", ["gym"], img=IMG_GYM),
    _ex("seated_cable_row", "Seated Cable Row", "سحب أرضي", "strength", ["back", "biceps"], "cable", ["gym"], img=IMG_GYM),
    _ex("shoulder_press", "Shoulder Press", "ضغط كتف", "strength", ["shoulders", "triceps"], "machine/free weights", ["gym"], img=IMG_GYM),
    _ex("lateral_raise", "Lateral Raise", "رفرفة جانبي", "strength", ["shoulders"], "dumbbells", ["gym"], img=IMG_GYM),
    _ex("biceps_curl", "Biceps Curl", "بايسبس كيرل", "strength", ["biceps"], "dumbbells", ["gym"], img=IMG_GYM),
    _ex("triceps_pushdown", "Triceps Pushdown", "ترايسبس كابل", "strength", ["triceps"], "cable", ["gym"], img=IMG_GYM),
    _ex("leg_press", "Leg Press", "ليج برس", "strength", ["quads", "glutes"], "machine", ["gym"], img=IMG_GYM),
    _ex("leg_extension", "Leg Extension", "فرد أمامي", "strength", ["quads"], "machine", ["gym"], img=IMG_GYM),
    _ex("leg_curl", "Leg Curl", "ثني خلفي", "strength", ["hamstrings"], "machine", ["gym"], img=IMG_GYM),
    _ex("barbell_squat", "Barbell Squat", "سكوات بار", "strength", ["quads", "glutes"], "barbell", ["gym"], "intermediate", ["core"], IMG_GYM),
    _ex("deadlift", "Deadlift", "ديدليفت", "strength", ["back", "hamstrings", "glutes"], "barbell", ["gym"], "advanced", ["core"], IMG_GYM),
    _ex("romanian_deadlift", "Romanian Deadlift", "ديدليفت روماني", "strength", ["hamstrings", "glutes"], "barbell/dumbbells", ["gym"], "intermediate", img=IMG_GYM),
    _ex("hip_thrust", "Hip Thrust", "هيب ثرست", "strength", ["glutes", "hamstrings"], "barbell/machine", ["gym"], img=IMG_GYM),
    _ex("cable_fly", "Cable Fly", "تفتيح كابل", "strength", ["chest"], "cable", ["gym"], img=IMG_GYM),
    _ex("treadmill_walk", "Treadmill Walk", "مشي على المشاية", "cardio", ["full_body"], "treadmill", ["gym"], img=IMG_CARDIO),
    _ex("stationary_bike", "Stationary Bike", "عجلة ثابتة", "cardio", ["legs"], "bike", ["gym"], img=IMG_CARDIO),
    _ex("elliptical", "Elliptical", "إليبتكال", "cardio", ["full_body"], "machine", ["gym"], img=IMG_CARDIO),
    _ex("cat_cow", "Cat-Cow Stretch", "تمرين القط والبقرة", "mobility", ["back"], "bodyweight", ["home", "gym"], img=IMG_MOBILITY),
    _ex("hip_flexor_stretch", "Hip Flexor Stretch", "إطالة الحوض", "mobility", ["legs", "glutes"], "bodyweight", ["home", "gym"], img=IMG_MOBILITY),
]


def get_exercise_by_id(exercise_id: str) -> ExerciseRecord | None:
    return next((e for e in EXERCISES_DB if e["id"] == exercise_id), None)


def filter_exercises(location: str | None = None, difficulty: str | None = None, muscle: str | None = None, goal: str | None = None, equipment: str | None = None, search: str | None = None, limit: int = 50, offset: int = 0) -> dict:
    q = (search or "").strip().lower()
    rows = []
    for ex in EXERCISES_DB:
        if location and location.lower() not in [x.lower() for x in ex["location"]]:
            continue
        if difficulty and ex["difficulty"].lower() != difficulty.lower():
            continue
        if muscle and muscle.lower() not in [x.lower() for x in ex["primary_muscles"] + ex["secondary_muscles"]]:
            continue
        if goal and goal.lower() not in [x.lower() for x in ex["goal_tags"]]:
            continue
        if equipment and equipment.lower() not in ex["equipment"].lower():
            continue
        if q and q not in ex["id"].lower() and q not in ex["name_en"].lower() and q not in ex["name_ar"].lower():
            continue
        rows.append(ex)
    return {"total": len(rows), "limit": limit, "offset": offset, "items": rows[offset: offset + limit]}


def get_exercise_categories() -> list[str]:
    return sorted({e["category"] for e in EXERCISES_DB})


def get_muscle_groups() -> list[str]:
    muscles = set()
    for e in EXERCISES_DB:
        muscles.update(e["primary_muscles"])
        muscles.update(e["secondary_muscles"])
    return sorted(muscles)
