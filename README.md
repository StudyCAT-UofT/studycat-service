# studycat-service

Repository for the CAT service for StudyCAT.

## Database Setup

The StudyCAT quiz engine uses a PostgreSQL database running in a Docker container. The connection details are stored in the `.env` file in the root directory.

For local development, duplicate the `.env.example` file in the root directory and name it `.env`

For local development, start Docker container with the local database server in the `studycat` repository by following the instructions in the README.md in the `studycat` repository.

Both the StudyCAT quiz engine (`studycat-service`) and the StudyCAT web application (`studycat`) use the same database. To ensure alignment between the two repositories, we are using Prisma to define the database schema and handle the database migrations. The `prisma` directory in the `studycat` repository contains this.

This repository includes the `studycat` repository as a submodule. This is done so that we can have a single place to define the database schema and handle the database migrations. We can find the submodule in the `external/studycat` directory. To avoid unnecessary files from being checked out, we are using a sparse checkout to only include the `prisma` directory.

To setup the submodule, run the following command:

```bash
./scripts/setup-submodules.sh
```

This will initialize the submodule and apply the sparse checkout. If the schema or migrations are updated in the `studycat` repository, you need to rerun this command to update the submodule.

To generate the Prisma client for the Python service, run the following command:

```bash
python -m prisma generate --schema external/studycat/prisma/schema.prisma --generator py
```

This needs to be run whenever the schema or migrations are updated in the `studycat` repository.

In the API, we use the Prisma client to interact with the database. The client is generated in the `db/client.py` file. To use the client, import `db` from `db.client`.
