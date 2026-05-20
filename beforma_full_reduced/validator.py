"""Plan validation checks for calories, macros, portions, diversity and image availability."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    detail: Optional[dict] = None


@dataclass
class ValidationResult:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)
    score: float = 100.0


def validate_plan(meals: list[dict], plan_totals: dict, target_calories: float, goal: str, calorie_tolerance: float = 0.06) -> ValidationResult:
    from meal_selector import GOAL_MACRO_RATIOS
    issues: list[ValidationIssue] = []
    score = 100.0

    cal_ratio = abs(plan_totals.get("calories", 0) - target_calories) / max(target_calories, 1)
    if cal_ratio > calorie_tolerance:
        issues.append(ValidationIssue(
            severity="error" if cal_ratio > 0.12 else "warning",
            code="CALORIE_MISMATCH",
            message=f"Daily calories off by {round(cal_ratio*100,1)}%",
            detail={"target": round(target_calories, 1), "actual": plan_totals.get("calories", 0)},
        ))
        score -= min(cal_ratio * 100, 30)

    ratios = GOAL_MACRO_RATIOS.get(goal, GOAL_MACRO_RATIOS["maintain"])
    total_cal = max(plan_totals.get("calories", 1), 1)
    actual = {
        "protein": (plan_totals.get("protein", 0) * 4) / total_cal,
        "carbs": (plan_totals.get("carbs", 0) * 4) / total_cal,
        "fat": (plan_totals.get("fat", 0) * 9) / total_cal,
    }
    for macro, target_ratio in ratios.items():
        diff = abs(actual[macro] - target_ratio)
        if diff > 0.10:
            issues.append(ValidationIssue(
                severity="warning",
                code=f"MACRO_RATIO_{macro.upper()}",
                message=f"{macro} ratio {round(actual[macro]*100,1)}% vs target {round(target_ratio*100,1)}%",
                detail={"macro": macro, "actual_pct": round(actual[macro]*100, 1), "target_pct": round(target_ratio*100, 1)},
            ))
            score -= diff * 30

    names = [m.get("name") for m in meals]
    if len(names) != len(set(names)):
        issues.append(ValidationIssue("warning", "DUPLICATE_MEALS", "Duplicate meals detected."))
        score -= 10

    sources = [m.get("protein_source") for m in meals if m.get("protein_source")]
    if len(sources) != len(set(sources)):
        issues.append(ValidationIssue("info", "PROTEIN_SOURCE_REPEATED", "Protein source repeated; acceptable but less diverse."))
        score -= 3

    for meal in meals:
        if not meal.get("image"):
            issues.append(ValidationIssue("warning", "MISSING_IMAGE", f"{meal.get('name')} has no image URL."))
            score -= 5
        if meal.get("calories", 0) < 150:
            issues.append(ValidationIssue("warning", "PORTION_TOO_SMALL", f"{meal.get('name')} is below 150 kcal."))
            score -= 4
        if meal.get("calories", 0) > 1400:
            issues.append(ValidationIssue("warning", "PORTION_TOO_LARGE", f"{meal.get('name')} is above 1400 kcal."))
            score -= 4

    score = max(0.0, round(score, 1))
    return ValidationResult(passed=not any(i.severity == "error" for i in issues), issues=issues, score=score)
