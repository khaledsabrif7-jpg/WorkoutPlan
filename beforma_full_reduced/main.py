"""BeForma AI Fitness & Nutrition API.

Anonymous API: no name, no email and no phone in request models or DB schema.
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Literal, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from database import GeneratedPlan, db_session, init_db
from exercises_db import EXERCISES_DB, filter_exercises, get_exercise_categories, get_muscle_groups
from food_cart_planner import generate_cart_based_plan, preview_cart
from foods_catalog import FOOD_CATALOG, filter_foods, get_categories_summary
from meal_generator import generate_full_meal_plan
from meals_db import MEALS_DB, count_by_type
from nutrition import activity_factor, calculate_bmi, generate_nutrition_plan, normalize_goal
from recommender import get_feedback_stats, get_meal_tags, rank_meals_for_goal, record_feedback, suggest_substitutions
from validator import validate_plan
from workout_generator import generate_workout_plan

API_VERSION = "1.0.0-reduced-food-db"
API_KEY = os.getenv("BEFORMA_API_KEY", "")
ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()]
INIT_DB_ON_STARTUP = os.getenv("INIT_DB_ON_STARTUP", "true").lower() == "true"

Goal = Literal["lose", "maintain", "gain"]
Gender = Literal["male", "female", "other", "m", "f"]
Strategy = Literal["strict", "flexible"]
MealType = Literal["breakfast", "lunch", "dinner", "snack"]
SelectionMode = Literal["ai_suggest", "user_cart"]

app = FastAPI(
    title="BeForma AI Fitness & Nutrition API",
    description="Anonymous fitness, nutrition, food-cart and workout recommendation API.",
    version=API_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    if INIT_DB_ON_STARTUP:
        try:
            init_db()
        except Exception:
            pass


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")


class SelectedFoodItem(BaseModel):
    food_id: str
    quantity_g: float = Field(..., ge=50, examples=[150])

    @field_validator("quantity_g")
    @classmethod
    def quantity_multiple_of_50(cls, value: float) -> float:
        if value % 50 != 0:
            raise ValueError("quantity_g must be a multiple of 50g")
        return value


class GeneratePlanRequest(BaseModel):
    age: int = Field(..., ge=10, le=100, examples=[24])
    gender: str = Field(..., examples=["male"])
    height: float = Field(..., ge=100, le=250, description="Height in cm", examples=[178])
    weight: float = Field(..., ge=30, le=300, description="Weight in kg", examples=[82])
    fitnessGoal: str = Field(..., examples=["lose"])
    activityLevel: str = Field("Sedentary", examples=["Sedentary"])
    experienceLevel: str = Field("Beginner", examples=["Beginner"])
    workoutLocation: str = Field("Home", examples=["Home"])
    dietaryPreference: str = Field("normal", examples=["normal"])
    selectionMode: SelectionMode = Field("ai_suggest", examples=["ai_suggest"])
    selectedFoods: list[SelectedFoodItem] = Field(default_factory=list)
    autoFillRemaining: bool = True
    allowOverflow: bool = False

    @field_validator("gender")
    @classmethod
    def normalize_gender(cls, value: str) -> str:
        v = value.strip().lower()
        if v == "m": return "male"
        if v == "f": return "female"
        if v not in {"male", "female", "other"}: return "other"
        return v


class CartPreviewRequest(BaseModel):
    age: int = Field(..., ge=10, le=100)
    gender: str
    height: float = Field(..., ge=100, le=250)
    weight: float = Field(..., ge=30, le=300)
    fitnessGoal: str
    activityLevel: str = "Sedentary"
    dietaryPreference: str = "normal"
    selectedFoods: list[SelectedFoodItem] = Field(default_factory=list)


class UserNutritionInput(BaseModel):
    age: int = Field(..., ge=10, le=100)
    gender: Gender
    height: float = Field(..., ge=100, le=250)
    weight: float = Field(..., ge=30, le=300)
    activity_level: float = Field(..., ge=1.0, le=2.2)
    goal: Goal


class MealPlanRequest(UserNutritionInput):
    num_meals: int = Field(3, ge=3, le=5)
    strategy: Strategy = "strict"
    dietary_preference: str = "normal"


class FeedbackRequest(BaseModel):
    meal_name: str
    accepted: bool


class ValidatePlanRequest(BaseModel):
    meals: list[dict]
    plan_totals: dict
    target_calories: float = Field(..., gt=0)
    goal: Goal
    calorie_tolerance: float = Field(0.06, ge=0.01, le=0.20)


class SubstitutionRequest(BaseModel):
    meal_name: str


class WorkoutGenerateRequest(BaseModel):
    fitnessGoal: str
    experienceLevel: str = "Beginner"
    workoutLocation: str = "Home"
    daysPerWeek: Optional[int] = Field(default=None, ge=2, le=6)


def choose_num_meals_for_client(goal: str, activity_level: str, experience_level: str) -> int:
    goal_norm = normalize_goal(goal)
    activity = (activity_level or "").strip().lower()
    level = (experience_level or "").strip().lower()
    if goal_norm == "gain":
        if any(word in activity for word in ["very", "super", "athlete", "active"]) or level in {"intermediate", "advanced"}:
            return 5
        return 4
    return 3


def save_generated_plan(request_id: str, payload: GeneratePlanRequest, response: dict) -> None:
    try:
        with db_session() as db:
            db.add(GeneratedPlan(
                request_id=request_id,
                age=payload.age,
                gender=payload.gender,
                height=payload.height,
                weight=payload.weight,
                fitness_goal=payload.fitnessGoal,
                activity_level=payload.activityLevel,
                experience_level=payload.experienceLevel,
                workout_location=payload.workoutLocation,
                dietary_preference=payload.dietaryPreference,
                selection_mode=payload.selectionMode,
                bmi=response.get("bmi"),
                bmi_category=response.get("bmi_category"),
                daily_calorie_target=response.get("daily_calorie_target"),
                macros_json=response.get("macros"),
                diet_plan_json=response.get("recommendations", {}).get("diet_plan"),
                workout_plan_json=response.get("recommendations", {}).get("workout_plan"),
                food_selection_json=response.get("food_selection"),
                raw_request_json=payload.model_dump(),
                raw_response_json=response,
            ))
    except Exception:
        pass


def _build_plan_response(payload: GeneratePlanRequest, full_plan: dict, nutrition_plan, bmi: float, bmi_category: str, workout_plan: dict, request_id: str, started: float, factor: float, goal: str, num_meals: int) -> dict:
    food_selection = full_plan.get("food_selection", {
        "mode": payload.selectionMode,
        "cart_total_calories": None,
        "target_calories": full_plan["daily_targets"]["daily_calories"],
        "remaining_before_autofill": None,
        "auto_fill_used": False,
        "user_selected_foods_count": 0,
        "auto_filled_foods_count": 0,
        "selected_categories": [],
    })
    return {
        "request_id": request_id,
        "status": "success",
        "user": {
            "age": payload.age,
            "gender": payload.gender,
            "height": payload.height,
            "weight": payload.weight,
        },
        "bmi": bmi,
        "bmi_category": bmi_category,
        "daily_calorie_target": full_plan["daily_targets"]["daily_calories"],
        "macros": {
            "protein_grams": full_plan["daily_targets"]["protein_grams"],
            "carbs_grams": full_plan["daily_targets"]["carbs_grams"],
            "fat_grams": full_plan["daily_targets"]["fat_grams"],
        },
        "recommendations": {
            "diet_plan": full_plan["meals"],
            "workout_plan": workout_plan,
        },
        "food_selection": food_selection,
        "plan_quality": {
            "quality_score": full_plan["quality_score"],
            "optimized": full_plan["optimized"],
            "accuracy": full_plan["accuracy"],
            "validation": full_plan["validation"],
        },
        "meta": {
            "api_version": API_VERSION,
            "activity_factor": factor,
            "normalized_goal": goal,
            "dietary_preference": payload.dietaryPreference,
            "num_meals": num_meals,
            "selection_mode": payload.selectionMode,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "catalog_meals_count": len(MEALS_DB),
            "food_catalog_count": len(FOOD_CATALOG),
            "exercises_count": len(EXERCISES_DB),
        },
    }


@app.get("/")
def root() -> dict:
    return {
        "service": "BeForma AI Fitness & Nutrition API",
        "version": API_VERSION,
        "docs": "/docs",
        "main_endpoint": "POST /generate-plan",
        "meals_count": len(MEALS_DB),
        "meals_by_type": count_by_type(),
        "foods_count": len(FOOD_CATALOG),
        "exercises_count": len(EXERCISES_DB),
    }


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "beforma-api",
        "version": API_VERSION,
        "main_endpoint": "/generate-plan",
        "meals_count": len(MEALS_DB),
        "meals_by_type": count_by_type(),
        "foods_count": len(FOOD_CATALOG),
        "exercises_count": len(EXERCISES_DB),
    }


@app.post("/generate-plan")
def generate_plan(payload: GeneratePlanRequest) -> dict:
    request_id = str(uuid.uuid4())
    t0 = time.perf_counter()
    goal = normalize_goal(payload.fitnessGoal)
    factor = activity_factor(payload.activityLevel)
    bmi, bmi_category = calculate_bmi(payload.height, payload.weight)
    nutrition_plan = generate_nutrition_plan(payload.age, payload.gender, payload.height, payload.weight, factor, goal)
    num_meals = choose_num_meals_for_client(payload.fitnessGoal, payload.activityLevel, payload.experienceLevel)

    if payload.selectionMode == "user_cart" and payload.selectedFoods:
        full_plan = generate_cart_based_plan(
            nutrition_plan=nutrition_plan,
            selected_foods=[x.model_dump() for x in payload.selectedFoods],
            num_meals=num_meals,
            goal=goal,
            dietary_preference=payload.dietaryPreference,
            auto_fill_remaining=payload.autoFillRemaining,
            allow_overflow=payload.allowOverflow,
        )
        if full_plan.get("fallback_to_ai"):
            full_plan = generate_full_meal_plan(nutrition_plan, num_meals=num_meals, strategy="strict", dietary_preference=payload.dietaryPreference)
    else:
        full_plan = generate_full_meal_plan(nutrition_plan, num_meals=num_meals, strategy="strict", dietary_preference=payload.dietaryPreference)

    workout_plan = generate_workout_plan(payload.fitnessGoal, payload.experienceLevel, payload.workoutLocation)
    response = _build_plan_response(payload, full_plan, nutrition_plan, bmi, bmi_category, workout_plan, request_id, t0, factor, goal, num_meals)
    save_generated_plan(request_id, payload, response)
    return response


@app.get("/foods")
def foods(category: Optional[str] = None, search: Optional[str] = None, dietaryPreference: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
    return {"status": "success", **filter_foods(category, search, dietaryPreference, limit, offset)}


@app.get("/foods/categories")
def food_categories() -> dict:
    return {"status": "success", "categories": get_categories_summary()}


@app.post("/cart/preview")
def cart_preview(payload: CartPreviewRequest) -> dict:
    goal = normalize_goal(payload.fitnessGoal)
    plan = generate_nutrition_plan(payload.age, payload.gender, payload.height, payload.weight, activity_factor(payload.activityLevel), goal)
    data = preview_cart([x.model_dump() for x in payload.selectedFoods], plan, payload.dietaryPreference)
    return {"status": "success", **data}


@app.get("/exercises")
def exercises(location: Optional[str] = None, difficulty: Optional[str] = None, muscle: Optional[str] = None, goal: Optional[str] = None, equipment: Optional[str] = None, search: Optional[str] = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict:
    return {"status": "success", **filter_exercises(location, difficulty, muscle, goal, equipment, search, limit, offset)}


@app.get("/exercises/categories")
def exercise_categories() -> dict:
    return {"status": "success", "categories": get_exercise_categories()}


@app.get("/exercises/muscles")
def exercise_muscles() -> dict:
    return {"status": "success", "muscles": get_muscle_groups()}


@app.post("/workout/generate")
def workout_generate(payload: WorkoutGenerateRequest) -> dict:
    return {"status": "success", "workout_plan": generate_workout_plan(payload.fitnessGoal, payload.experienceLevel, payload.workoutLocation, payload.daysPerWeek)}


@app.post("/api/v1/nutrition/targets", dependencies=[Depends(require_api_key)])
def calculate_targets(payload: UserNutritionInput) -> dict:
    plan = generate_nutrition_plan(payload.age, payload.gender, payload.height, payload.weight, payload.activity_level, payload.goal)
    return {"request_id": str(uuid.uuid4()), "status": "success", "targets": plan.as_dict(), "input": payload.model_dump()}


@app.post("/api/v1/nutrition/meal-plan", dependencies=[Depends(require_api_key)])
def generate_meal_plan(payload: MealPlanRequest) -> dict:
    plan = generate_nutrition_plan(payload.age, payload.gender, payload.height, payload.weight, payload.activity_level, payload.goal)
    full_plan = generate_full_meal_plan(plan, num_meals=payload.num_meals, strategy=payload.strategy, dietary_preference=payload.dietary_preference)
    return {"request_id": str(uuid.uuid4()), "status": "success", "data": full_plan}


@app.get("/api/v1/nutrition/meals", dependencies=[Depends(require_api_key)])
def meals_catalog(meal_type: Optional[MealType] = None, tag: Optional[str] = Query(default=None), limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)) -> dict:
    meals = [m for m in MEALS_DB if meal_type is None or m["meal_type"] == meal_type]
    enriched = []
    for meal in meals:
        item = dict(meal)
        item["tags"] = get_meal_tags(meal["name"])
        if tag is None or tag.lower() in [t.lower() for t in item["tags"]]:
            enriched.append(item)
    return {"status": "success", "count": len(enriched), "limit": limit, "offset": offset, "meals": enriched[offset: offset + limit]}


@app.get("/api/v1/nutrition/recommendations", dependencies=[Depends(require_api_key)])
def recommendations(goal: Goal, meal_type: Optional[MealType] = None, dietary_preference: str = "normal", n: int = Query(5, ge=1, le=20)) -> dict:
    meals = rank_meals_for_goal(goal, meal_type=meal_type, top_n=n, dietary_preference=dietary_preference)
    enriched = []
    for meal in meals:
        item = dict(meal)
        item["tags"] = get_meal_tags(meal["name"])
        item["substitutions"] = suggest_substitutions(meal["name"])
        enriched.append(item)
    return {"status": "success", "goal": goal, "meal_type": meal_type, "dietary_preference": dietary_preference, "meals": enriched}


@app.post("/api/v1/nutrition/substitutions", dependencies=[Depends(require_api_key)])
def substitutions(payload: SubstitutionRequest) -> dict:
    if not any(m["name"] == payload.meal_name for m in MEALS_DB):
        raise HTTPException(status_code=404, detail="Meal not found in catalog.")
    return {"status": "success", "meal_name": payload.meal_name, "tags": get_meal_tags(payload.meal_name), "substitutions": suggest_substitutions(payload.meal_name)}


@app.post("/api/v1/nutrition/validate-plan", dependencies=[Depends(require_api_key)])
def validate_existing_plan(payload: ValidatePlanRequest) -> dict:
    result = validate_plan(payload.meals, payload.plan_totals, payload.target_calories, payload.goal, payload.calorie_tolerance)
    return {"status": "success", "validation": {"passed": result.passed, "score": result.score, "issues": [i.__dict__ for i in result.issues]}}


@app.post("/api/v1/nutrition/feedback", dependencies=[Depends(require_api_key)])
def feedback(payload: FeedbackRequest) -> dict:
    if not any(m["name"] == payload.meal_name for m in MEALS_DB):
        raise HTTPException(status_code=404, detail="Meal not found in catalog.")
    record_feedback(payload.meal_name, payload.accepted)
    return {"status": "success", "message": "Anonymous feedback recorded", "meal_name": payload.meal_name, "accepted": payload.accepted}


@app.get("/api/v1/nutrition/feedback/stats", dependencies=[Depends(require_api_key)])
def feedback_stats() -> dict:
    return {"status": "success", "data": get_feedback_stats()}
