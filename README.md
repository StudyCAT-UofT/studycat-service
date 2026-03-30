# StudyCAT Quiz Engine Service

A FastAPI-based adaptive testing service that uses Item Response Theory (IRT) models to provide personalized quiz experiences. The service integrates with a SQL Server database and implements both Unidimensional and Multidimensional IRT models using AdaptiveTesting for item selection.

## API Endpoints

### Health Check

- `GET /v1/health` - Service health status

### Quiz Management

- `POST /v1/attempts/{attempt_id}/init` - Initialize a quiz attempt and get first question
- `POST /v1/attempts/{attempt_id}/step` - Process response and get next question

## Quick Start

### Prerequisites

1. **Python 3.13+**
2. **SQL Server database** (see Database Setup below)
3. **Environment variables** (see Configuration below)

### Details

The StudyCAT quiz engine uses a SQL Server database running in a Docker container. The connection details are stored in the .env file in the root directory.

For local development, duplicate the .env.example file in the root directory and name it .env

For local development, start the Docker container with the local database server in the studycat repository by following the instructions in the README.md in the studycat repository.

Both the StudyCAT quiz engine (`studycat-service`) and the StudyCAT web application (`studycat`) use the same database. To ensure alignment between the two repositories, we are using Prisma to define the database schema and handle the database migrations. The `studycat-schema` repository contains the Prisma schema and migrations for the database.

This repository installs the `studycat-schema` repository as a submodule.

### Installation

1. **Clone the repository:**

   ```bash
   git clone <repository-url>
   cd studycat-service
   ```

2. **Create virtual environment and install dependencies:**

   ```bash
   make venv install
   ```

3. **Set up database submodule:**

   ```bash
   make submodule-update
   ```

4. **Generate Prisma client:**

   ```bash
   make db-generate
   ```

5. **Configure environment:**

   ```bash
   cp .env.example .env
   # Edit .env with your database connection details
   ```

6. **Start the service:**
   ```bash
   make run
   ```

## API Usage Examples

### Initialize Quiz Attempt

```bash
curl -X POST "http://localhost:8000/v1/attempts/{attempt_id}/init" \
  -H "Content-Type: application/json" \
  -d '{
    "modules": ["Testing", "Architecture"],
    "prior_mu": 0.0,
    "prior_sigma2": 1.0
  }'
```

**Response:**

```json
{
  "theta": { "Testing": 0.0, "Architecture": 0.0 },
  "next_item": {
    "item_id": "item_123",
    "skill": "Testing",
    "stem": "What is the primary purpose of unit testing?",
    "options": ["Option A", "Option B", "Option C", "Option D"]
  },
  "next_action": "CONTINUE"
}
```

### Process Response

```bash
curl -X POST "http://localhost:8000/v1/attempts/{attempt_id}/step" \
  -H "Content-Type: application/json" \
  -d '{
    "response_id": "response_456"
  }'
```

**Response:**

```json
{
  "theta": { "Testing": 0.5, "Architecture": 0.2 },
  "mastery": { "Testing": true, "Architecture": false },
  "next_action": "CONTINUE",
  "next_item": {
    "item_id": "item_789",
    "skill": "Architecture",
    "stem": "Design a microservices architecture...",
    "options": ["Option A", "Option B", "Option C", "Option D"]
  }
}
```

### `next_action` Values

The `next_action` field in step responses drives client-side navigation:

| Value | Meaning |
|-------|---------|
| `CONTINUE` | Another item is available; display `next_item`. |
| `FINISH` | The fixed question limit has been reached; show results. |
| `MASTERED` | Every skill has crossed its mastery threshold; show the mastery screen. Takes precedence over `FINISH` if both conditions are met. |

## Architecture

### Core Components

- **`main.py`** - FastAPI application with database lifespan management
- **`routers.py`** - API route definitions and request/response handling
- **`schemas.py`** - Pydantic models for request/response validation
- **`service/core.py`** - Main business logic and IRT model integration
- **`db/repo.py`** - Database repository layer with Prisma queries
- **`engine/adapter.py`** - IRT model adapter and item selection logic
- **`models/`** - IRT model implementations (Unidimensional/Multidimensional)

### Data Flow

1. **Core Backend** creates Attempt and Response records
2. **Quiz Engine** validates attempts and fetches eligible items by module
3. **IRT Models** select optimal next questions based on ability estimates
4. **Engine** updates theta values, persists to database, and stores snapshots
5. **API** returns next question and updated ability estimates

### IRT Integration

The service implements:

- **Unidimensional IRT**: Single ability estimation per skill
- **Multidimensional IRT**: Multiple correlated abilities
- **Bayesian Estimation**: Uses BayesModal with NormalPrior
- **Item Selection**: Maximum Information Criterion for optimal selection

### Mastery System

Each quiz has per-module mastery thresholds stored in `QuizModule.masteryThreshold`. After every response, the engine compares each skill's theta estimate against its threshold. When theta exceeds the threshold the skill is marked mastered (`mastery: { "SkillName": true }`). Once all skills in the attempt are mastered the step response returns `next_action: "MASTERED"`.

### Theta Persistence

Theta values (ability estimates) are persisted per enrollment and module in the `Theta` table. On `init`, the engine loads any previously stored thetas for the enrollment and seeds the IRT model with them, so ability estimates carry over across attempts for the same student and quiz.

### Repeat-Correct-Question Filtering

If a quiz has `repeatCorrectQuestions` set to `false`, the engine automatically removes any items the student has previously answered correctly (across all past attempts for that quiz and enrollment) before building the item pool. If no unanswered items remain after filtering, the attempt ends immediately.

## Development

### Project Structure

```
studycat-service/
├── main.py                 # FastAPI application
├── routers.py              # API routes
├── schemas.py              # Pydantic models
├── config.py               # Settings
├── requirements.txt        # Python dependencies
├── Makefile                # Dev task runner
├── pyproject.toml          # Linting/tool config
├── service/
│   └── core.py             # Main business logic
├── db/
│   ├── client.py           # Prisma client singleton
│   └── repo.py             # Database queries
├── engine/
│   └── adapter.py          # IRT model adapter
├── models/
│   ├── unidimensional.py   # Unidimensional IRT model
│   ├── multidimensional.py # Multidimensional IRT model
│   └── README.md           # Models documentation
├── tests/
│   └── test_core.py        # Unit tests
└── external/
    └── studycat-schema/    # Database schema (submodule)
```

### Testing

```bash
# Run unit tests
make test

# Run with coverage report
make test-coverage

# Test health endpoint manually
curl -X GET "http://localhost:8000/v1/health"
```
