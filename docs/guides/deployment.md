# Deployment

This guide covers how to deploy the QuoinAPI application using Docker.

## 🐳 Docker Deployment

The project includes a production-ready `Dockerfile` and `docker-compose.yml`
for containerized deployment.

---

## Local Docker Development

Run the entire stack (Application + PostgreSQL Database) locally using Docker
Compose:

```bash
just up
```

This command:

- Builds the application Docker image
- Starts PostgreSQL container
- Starts the application container
- Configures networking between containers

Access the application at [http://localhost:8000](http://localhost:8000).

### Stop Containers

To stop and remove all containers:

```bash
just down
```

---

## Production Deployment

### Building the Production Image

Build the Docker image manually for production:

```bash
docker build -t quoin-api:latest .
```

The `Dockerfile` is optimized for production with:

- **Multi-stage build** - Smaller final image size
- **Non-root user** - Enhanced security
- **Layer caching** - Faster rebuilds
- **Production dependencies only** - No dev tools

### Running in Production

**With Docker Compose:**

```bash
docker-compose up -d
```

**With Docker CLI:**

```bash
# Run PostgreSQL
docker run -d \
  --name postgres \
  -e QUOIN_POSTGRES_USER=postgres \
  -e QUOIN_POSTGRES_PASSWORD=postgres \
  -e QUOIN_POSTGRES_DB=app_db \
  -p 5432:5432 \
  postgres:17-alpine

# Run Application
docker run -d \
  --name quoin-api \
  --link postgres:db \
  -p 8000:8000 \
  -e QUOIN_POSTGRES_HOST=db \
  quoin-api:latest
```

---

## Environment Variables

Configure the application using environment variables. See
[Configuration Guide](configuration.md) for all available options.

**Production Essentials:**

```bash
# Application
QUOIN_ENV=production
QUOIN_OTEL_ENABLED=true

# Database
QUOIN_POSTGRES_HOST=db
QUOIN_POSTGRES_PORT=5432
QUOIN_POSTGRES_USER=postgres
QUOIN_POSTGRES_PASSWORD=<strong-password>
QUOIN_POSTGRES_DB=app_db
```

> **Security Warning**: Never commit `.env` files with production credentials to
> version control!

---

## Cloud Deployment

The Docker image can be deployed to any container platform:

### Recommended Platforms

- **Railway** - [railway.app](https://railway.app)
- **Render** - [render.com](https://render.com)
- **Fly.io** - [fly.io](https://fly.io)
- **Google Cloud Run** - Serverless containers
- **AWS ECS** - Elastic Container Service
- **Azure Container Apps** - Managed containers

### Example: Railway Deployment

1. **Connect Repository**: Link your GitHub repository to Railway
2. **Add PostgreSQL**: Add a PostgreSQL database service
3. **Configure Environment Variables**: Set all required environment variables
4. **Deploy**: Railway automatically builds and deploys from `Dockerfile`

---

## Health Checks

The application includes a health check endpoint for monitoring:

```bash
curl http://localhost:8000/api/v1/system/health
```

Expected response:

```json
{
  "status": "healthy",
  "database": "connected"
}
```

Use this endpoint for:

- **Docker health checks** - `HEALTHCHECK` directive
- **Load balancer probes** - Kubernetes liveness/readiness
- **Monitoring systems** - Uptime tracking

---

## See Also

- [Release Workflow](release-workflow.md) — Version management and tagging
- [Observability](observability.md) — Setting up logs and traces
- [Troubleshooting](troubleshooting.md) — Common deployment issues
- [Dockerfile](https://github.com/balakmran/quoin-api/blob/main/Dockerfile) — Production image configuration
