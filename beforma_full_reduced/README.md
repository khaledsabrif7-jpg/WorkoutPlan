# BeForma AI Fitness & Nutrition API

Anonymous FastAPI backend for fitness, nutrition, food-cart meal planning and workout recommendations.

## What is included

- BMI, BMR, TDEE and goal-based calorie/macro targets.
- AI Suggest Mode for automatic meal recommendations.
- User Food Cart Mode where the cart capacity equals the user's daily calories.
- Reduced practical food catalog: 92 foods instead of a huge 700-item database.
- Generated meal database: 112 meals while preserving the old selector/optimizer/validator algorithm.
- Workout system with exercise images, instructions, sets, reps and rest.
- Swagger docs at `/docs`.
- Railway-ready Docker deployment.
- Postman collection.
- Local evaluation script.

## Privacy

This API is anonymous. It does **not** require or store:

- name
- email
- phone

## Run locally

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open:

```text
http://localhost:8000/docs
http://localhost:8000/health
```

## Main endpoint

```http
POST /generate-plan
```

### AI Suggest Mode

```json
{
  "age": 24,
  "gender": "male",
  "height": 178,
  "weight": 82,
  "fitnessGoal": "lose",
  "activityLevel": "Sedentary",
  "experienceLevel": "Beginner",
  "workoutLocation": "Home",
  "dietaryPreference": "normal",
  "selectionMode": "ai_suggest"
}
```

### User Cart Mode

```json
{
  "age": 24,
  "gender": "male",
  "height": 178,
  "weight": 82,
  "fitnessGoal": "gain",
  "activityLevel": "Moderately Active",
  "experienceLevel": "Intermediate",
  "workoutLocation": "Gym",
  "dietaryPreference": "normal",
  "selectionMode": "user_cart",
  "selectedFoods": [
    {"food_id": "chicken_breast_cooked", "quantity_g": 200},
    {"food_id": "rice_white_cooked", "quantity_g": 250},
    {"food_id": "banana", "quantity_g": 100}
  ],
  "autoFillRemaining": true,
  "allowOverflow": false
}
```

## Food cart logic

- Each food item stores calories, protein, carbs and fat per 50g.
- The user adds food in 50g steps.
- Cart capacity equals daily calorie target.
- If the cart is incomplete, the API auto-fills missing calories/macros.
- Dietary preferences are respected: vegan, vegetarian, pescatarian, dairy_free, gluten_free.
- If the cart exceeds the target by more than 5%, the API returns `CART_OVERFLOW` unless `allowOverflow=true`.

## Useful endpoints

```text
GET  /health
GET  /foods
GET  /foods/categories
POST /cart/preview
GET  /exercises
GET  /exercises/categories
GET  /exercises/muscles
POST /workout/generate
POST /generate-plan
```

## Evaluation

```bash
python evaluate_local_accuracy.py
```

This creates `accuracy_report.csv` and prints a summary.

## Railway

1. Push the files to GitHub.
2. Railway → New Project → Deploy from GitHub Repo.
3. Variables:

```env
ALLOWED_ORIGINS=*
INIT_DB_ON_STARTUP=true
DATABASE_URL=${{Postgres.DATABASE_URL}}
```

The service uses:

```text
/health
```

as the health check path.

## Note

This project is for fitness guidance and macro matching. It is not medical diagnosis or medical nutrition therapy.
