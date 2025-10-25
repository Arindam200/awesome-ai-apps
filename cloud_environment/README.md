# Claude AI Cloud Environment

A comprehensive cloud deployment solution for Claude AI applications with support for AWS, GCP, Azure, and local development using Docker.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Quick Start](#quick-start)
- [Local Development](#local-development)
- [Cloud Deployment](#cloud-deployment)
  - [AWS Deployment](#aws-deployment)
  - [GCP Deployment](#gcp-deployment)
  - [Azure Deployment](#azure-deployment)
- [Configuration](#configuration)
- [Architecture](#architecture)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

## Overview

This cloud environment provides a production-ready infrastructure for deploying Claude AI applications. It includes:

- Dockerized application setup
- Multi-cloud deployment support (AWS, GCP, Azure)
- Local development environment with Docker Compose
- Reverse proxy with Nginx
- Database and caching support (PostgreSQL, Redis)
- Security best practices
- CI/CD pipeline templates

## Features

- **Multi-Cloud Support**: Deploy to AWS ECS, GCP Cloud Run, or Azure Container Instances
- **Containerized**: Fully Dockerized with multi-stage builds
- **Scalable**: Auto-scaling configurations for cloud deployments
- **Secure**: Environment variable management, secrets handling, and security headers
- **Development Ready**: Local development environment with hot-reload
- **Production Ready**: Health checks, logging, and monitoring
- **Infrastructure as Code**: Deployment scripts and configurations

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+
- Cloud CLI tools (optional, for cloud deployment):
  - AWS CLI
  - gcloud CLI
  - Azure CLI

### Setup

1. Clone the repository and navigate to the cloud_environment directory:

```bash
cd awesome-ai-apps/cloud_environment
```

2. Run the setup script:

```bash
./scripts/setup.sh
```

3. Edit the configuration file:

```bash
vim config/.env
```

Add your Anthropic API key and other required configuration.

## Local Development

### Starting the Environment

Start all services locally using Docker Compose:

```bash
./scripts/start-local.sh
```

This will start:
- Claude AI Application (port 8000)
- PostgreSQL Database (port 5432)
- Redis Cache (port 6379)
- Nginx Reverse Proxy (port 80)

### Accessing Services

- Main Application: http://localhost:8000
- Nginx Proxy: http://localhost:80
- Health Check: http://localhost:8000/health

### Viewing Logs

```bash
cd docker
docker-compose logs -f
```

### Stopping Services

```bash
./scripts/stop-local.sh
```

### Cleanup

To remove all containers, volumes, and images:

```bash
./scripts/cleanup.sh
```

## Cloud Deployment

### AWS Deployment

Deploy to AWS ECS with Fargate:

```bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=your_account_id
./deployment/aws/deploy.sh
```

**Prerequisites:**
- AWS CLI configured with credentials
- AWS account with ECS permissions
- ECR repository access

**Resources Created:**
- ECS Cluster
- ECS Service with Fargate
- ECR Repository
- Task Definition
- CloudWatch Log Groups

### GCP Deployment

Deploy to Google Cloud Run:

```bash
export GCP_PROJECT_ID=your_project_id
export GCP_REGION=us-central1
./deployment/gcp/deploy.sh
```

**Prerequisites:**
- gcloud CLI authenticated
- GCP project with billing enabled
- Cloud Run API enabled

**Resources Created:**
- Cloud Run Service
- Container Registry images
- Secret Manager secrets

### Azure Deployment

Deploy to Azure Container Instances:

```bash
export AZURE_RESOURCE_GROUP=claude-ai-rg
export AZURE_LOCATION=eastus
export AZURE_ACR_NAME=claudeairegistry
./deployment/azure/deploy.sh
```

**Prerequisites:**
- Azure CLI authenticated
- Azure subscription
- Resource group permissions

**Resources Created:**
- Resource Group
- Container Registry (ACR)
- Container Instance
- Key Vault for secrets

## Configuration

### Environment Variables

Key configuration options in `config/.env`:

```bash
# Required
ANTHROPIC_API_KEY=your_api_key

# Application
ENVIRONMENT=development|production
LOG_LEVEL=DEBUG|INFO|WARNING|ERROR
PORT=8000

# Database (optional)
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=claudedb

# Redis (optional)
REDIS_HOST=redis
REDIS_PORT=6379

# Cloud specific
AWS_REGION=us-east-1
GCP_PROJECT_ID=your-project
AZURE_RESOURCE_GROUP=your-rg
```

### Docker Compose Configuration

Modify `docker/docker-compose.yml` to:
- Adjust resource limits (CPU, memory)
- Enable/disable services
- Configure networking
- Add custom volumes

### Nginx Configuration

Customize `config/nginx.conf` for:
- SSL/TLS configuration
- Rate limiting
- Custom routing
- Security headers

## Architecture

### Local Development Architecture

```
┌─────────────────────┐
│   Nginx (Port 80)   │
│  Reverse Proxy      │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  Claude AI App      │
│   (Port 8000)       │
└─────┬───────┬───────┘
      │       │
      │       └─────────┐
      │                 │
┌─────▼─────┐   ┌──────▼──────┐
│ PostgreSQL│   │    Redis    │
│ (Port 5432│   │ (Port 6379) │
└───────────┘   └─────────────┘
```

### Cloud Architecture (AWS Example)

```
Internet
   │
   ▼
Application Load Balancer
   │
   ▼
ECS Fargate Service
   │
   ├──► Task 1 (Container)
   ├──► Task 2 (Container)
   └──► Task N (Container)
        │
        ├──► RDS (PostgreSQL)
        └──► ElastiCache (Redis)
```

## Monitoring

### Health Checks

All deployments include health check endpoints:

```bash
curl http://your-service-url/health
```

### Viewing Logs

**Local:**
```bash
docker-compose logs -f
```

**AWS:**
```bash
aws ecs describe-tasks --cluster claude-ai-app-cluster
```

**GCP:**
```bash
gcloud run services logs read claude-ai-app --region us-central1
```

**Azure:**
```bash
az container logs --resource-group claude-ai-rg --name claude-ai-app-container
```

## Troubleshooting

### Common Issues

#### Docker Build Fails

```bash
# Clear Docker cache
docker system prune -a

# Rebuild without cache
docker-compose build --no-cache
```

#### Permission Denied on Scripts

```bash
chmod +x scripts/*.sh
chmod +x deployment/*/*.sh
```

#### Port Already in Use

```bash
# Change ports in docker-compose.yml or stop conflicting services
lsof -i :8000
kill -9 <PID>
```

#### API Key Not Found

Ensure your `.env` file exists and contains:
```bash
ANTHROPIC_API_KEY=your_actual_key_here
```

### Getting Help

- Check logs: `docker-compose logs -f`
- Verify configuration: `cat config/.env`
- Test connectivity: `docker-compose ps`
- Review documentation: See individual service READMEs

## Security Best Practices

1. **Never commit `.env` files** - Use `.env.example` as template
2. **Use secrets management** - AWS Secrets Manager, GCP Secret Manager, Azure Key Vault
3. **Enable HTTPS** - Configure SSL certificates in nginx.conf
4. **Rotate API keys regularly**
5. **Use least privilege IAM roles**
6. **Enable monitoring and alerting**
7. **Keep dependencies updated**

## Contributing

Contributions are welcome! Please read the main repository's CONTRIBUTING.md for guidelines.

## License

This project is part of the awesome-ai-apps repository and follows the same MIT License.

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review logs and error messages

## Next Steps

1. **Customize for your use case**: Modify Docker configurations
2. **Add monitoring**: Integrate with Datadog, New Relic, or Sentry
3. **Set up CI/CD**: Use the GitHub Actions workflows
4. **Scale up**: Configure auto-scaling policies
5. **Secure**: Add authentication and authorization
6. **Optimize**: Profile and tune performance

---

Built with support for Claude AI applications. Deploy anywhere, run everywhere.
