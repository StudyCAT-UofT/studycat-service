# StudyCAT IRT API (Skeleton)

This is a minimal FastAPI backend for adaptive testing using Item Response Theory (IRT). It provides a clean skeleton: web API, session management, and dataset loading are implemented, while the actual IRT math is abstracted behind an adapter (`irt_adapter.py`) to allow for an external library plug in later.

---

## Project Structure

```
studycat_api/  
- requirements.txt – Python dependencies  
- main.py – FastAPI entrypoint  
- config.py – Global settings (dataset path, limits, CORS)  
- schemas.py – Pydantic request/response models  
- dataset.py – Dataset loader (CSV/XLSX) + item representation  
- irt_adapter.py – Thin wrapper around an external IRT library  
- session_service.py – Business logic: sessions, updates, stop rules  
- routers.py – FastAPI routes (/v1 endpoints)
```

---

## Running Locally

1. Install Python 3.10+  
2. Install dependencies: `pip install -r requirements.txt`  
3. Run the server: `uvicorn main:app --reload --port 8000`  
4. Open the docs at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## API Endpoints

- **GET /v1/health** – Liveness check  
- **POST /v1/session/init** – Start a session  
  - Input: concepts, max_items, prior_mu, prior_sigma2  
  - Output: session_id, theta, next_item  
- **POST /v1/session/step** – Submit the previous answer and get the next item  
  - Input: session_id, item_id, answer_index  
  - Output: updated theta, mastery, next_action, next_item  
- **POST /v1/session/state** – Diagnostic snapshot  
  - Input: session_id  
  - Output: theta, asked_items, remaining_items, mastery  

---

## Frontend Usage

1. Call `/session/init` and render the returned `next_item`  
2. On each answer, call `/session/step` with `session_id`, `item_id`, and `answer_index`, then render the new `next_item`  
3. Stop when `next_action = FINISH`  
4. Use `/session/state` to restore state after a page reload

---

## What Works Now

- Session lifecycle (init → step → finish)  
- Dataset loading (CSV/XLSX)  
- In-memory session storage  
- Placeholder θ updates (+0.1 or –0.1) and random item selection  
- Documented endpoints with schema validation  

---

## What Needs Implementation

- Ensure dataset has columns: `item_id`, `stem`, `options`, `correct_index`, `concept`, `IRT_a`, `IRT_b`, `IRT_c`  
- Replace stubs in `irt_adapter.py` with calls to your external IRT library  
- Make item selection deterministic (max-information instead of random)  
- Replace in-memory session store with Redis/Postgres for production  
- Enable CORS in `main.py` if frontend runs on a different origin  
- Add authentication if needed  
- Refine stopping rules beyond `max_items` (e.g., information thresholds)

---

## Testing

- Run server, open `/docs`, and test endpoints interactively  
- Confirm init returns a first item  
- Confirm step updates theta and advances until finish  
- Confirm invalid input returns 400/404  

---

## Summary

This repository provides a working skeleton: frontend can call `/init`, `/step`, and `/state` to simulate adaptive testing. All IRT math is stubbed behind `irt_adapter.py` so you can drop in your external library later without touching the API or session flow.p
