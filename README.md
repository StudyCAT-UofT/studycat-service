# StudyCAT Quiz Engine Service

A FastAPI-based adaptive testing service that uses Item Response Theory (IRT) models to provide personalized quiz experiences. The service integrates with a PostgreSQL database and implements both Unidimensional and Multidimensional IRT models using AdaptiveTesting for item selection.

## API Endpoints

### Health Check

- `GET /v1/health` - Service health status

### Quiz Management

- `POST /v1/attempts/{attempt_id}/init` - Initialize a quiz attempt and get first question
- `POST /v1/attempts/{attempt_id}/step` - Process response and get next question

## Quick Start

### Prerequisites

1. **Python 3.13+**
2. **PostgreSQL database** (see Database Setup below)
3. **Environment variables** (see Configuration below)

### Details

The StudyCAT quiz engine uses a PostgreSQL database running in a Docker container. The connection details are stored in
the .env file in the root directory.

For local development, duplicate the .env.example file in the root directory and name it .env

For local development, start Docker container with the local database server in the studycat repository by following the instructions in the README.md in the studycat repository.

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

### Test Database Connection

```bash
python db/test_db.py
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

## Development

### Project Structure

```
studycat-service/
├── main.py                 # FastAPI application
├── routers.py              # API routes
├── schemas.py              # Pydantic models
├── requirements.txt        # Python dependencies
├── service/
│   ├── core.py            # Main business logic
├── db/
│   ├── client.py          # Prisma client
│   ├── repo.py            # Database queries
│   └── test_db.py         # Database testing
├── engine/
│   └── adapter.py         # IRT model adapter
├── models/
│   ├── unidimensional.py  # Unidimensional IRT model
│   └── multidimensional.py # Multidimensional IRT model
└── external/
    └── studycat-schema/   # Database schema (submodule)
```

### Testing

1. **Database Connection Test:**

   ```bash
   python db/test_db.py
   ```

2. **API Testing:**

   ```bash
   # Start service
   uvicorn main:app --reload

   # Test health endpoint
   curl -X GET "http://localhost:8000/v1/health"

   # Test with real database data
   # (Use existing attempt IDs from your database)
   ```
