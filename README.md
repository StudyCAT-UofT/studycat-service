# studycat-service

Repository for the CAT service for StudyCAT.

## Database setup

The StudyCAT quiz engine uses a PostgreSQL database running in a Docker container. The connection details are stored in the .env file in the root directory.

### Getting started

For local development, duplicate the .env.example file in the root directory and name it .env

For local development, start Docker container with the local database server in the studycat repository by following the instructions in the README.md in the studycat repository.

Both the StudyCAT quiz engine (`studycat-service`) and the StudyCAT web application (`studycat`) use the same database. To ensure alignment between the two repositories, we are using Prisma to define the database schema and handle the database migrations. The `studycat-schema` repository contains the Prisma schema and migrations for the database.

This repository installs the `studycat-schema` repository as a submodule.

When cloning the repository for the first time, to setup the submodule, run the following command in the root directory of this repository:

```bash
git submodule update --init --recursive
```

Make sure you have the Prisma pip package installed. You can install it by running the following command:

```bash
pip install -U prisma
```

To use Prisma, you need to generate the Prisma client. You can generate the client by running the following command in the root directory of this repository:

```bash
python -m prisma generate --schema external/studycat-schema/schema.prisma --generator py
```

### Development workflow

When pulling the latest changes from the repository, to update the submodule to the latest version, run the following command in the root directory of this repository:

```bash
git submodule update --remote
```

Regenerate the Prisma client when making changes to the schema by running the following command in the root directory of this repository:

```bash
python -m prisma generate --schema external/studycat-schema/schema.prisma --generator py
```

To connect to the database, you can use the `db` client in the `db` directory. You can use the `db` client to query the database.

```python
from db.client import db
```

## Hardcoded Version (For Frontend Development)

This repository includes a hardcoded version of the service that returns mock data without requiring database setup. This is useful for frontend development and testing API endpoints.

### Quick Start (Hardcoded Version)

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the service:**
   ```bash
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Test the endpoints:**
   ```bash
   # Health check
   curl -X GET "http://localhost:8000/v1/health"
   
   # Initialize an attempt
   curl -X POST "http://localhost:8000/v1/attempt/init" \
     -H "Content-Type: application/json" \
     -d '{"attempt_id": "test_001"}'
   
   # Answer a question
   curl -X POST "http://localhost:8000/v1/attempt/step" \
     -H "Content-Type: application/json" \
     -d '{"attempt_id": "test_001", "item_id": "item_001", "answer_index": 0}'
   ```

### API Endpoints (Hardcoded Version)

- `GET /v1/health` - Health check endpoint
- `POST /v1/attempt/init` - Initialize a new quiz attempt
- `POST /v1/attempt/step` - Submit an answer and get the next question

### Sample Data

The hardcoded version includes 5 sample questions. The service tracks attempt state in memory and provides a simple progression through the questions.

### Switching Between Versions

- **Hardcoded version**: Uses `service/core_hardcoded.py` (current default)
- **Database version**: Uses `service/core.py` (TODO: requires database setup)

To switch to the database version (not yet implemented), update the import in `routers.py`:
```python
# Change this line in routers.py
from service.core_hardcoded import init_attempt, step_attempt, PublicItem
# To this:
from service.core import init_attempt, step_attempt, PublicItem
```
