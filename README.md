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
