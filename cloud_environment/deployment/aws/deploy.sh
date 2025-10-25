#!/bin/bash

# AWS Deployment Script for Claude AI Applications
# This script deploys the application to AWS ECS with Fargate

set -e

# Configuration
APP_NAME="claude-ai-app"
REGION="${AWS_REGION:-us-east-1}"
ECR_REPO_NAME="${APP_NAME}-repo"
CLUSTER_NAME="${APP_NAME}-cluster"
SERVICE_NAME="${APP_NAME}-service"
TASK_FAMILY="${APP_NAME}-task"

echo "=========================================="
echo "Deploying Claude AI Application to AWS"
echo "=========================================="

# Check AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo "Error: AWS CLI is not installed. Please install it first."
    exit 1
fi

# Check if logged in to AWS
aws sts get-caller-identity > /dev/null 2>&1 || {
    echo "Error: Not authenticated with AWS. Please run 'aws configure'."
    exit 1
}

echo "Step 1: Creating ECR repository..."
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${REGION} 2>/dev/null || \
    aws ecr create-repository --repository-name ${ECR_REPO_NAME} --region ${REGION}

# Get ECR repository URI
ECR_URI=$(aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${REGION} --query 'repositories[0].repositoryUri' --output text)
echo "ECR Repository: ${ECR_URI}"

echo "Step 2: Logging in to ECR..."
aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}

echo "Step 3: Building Docker image..."
cd ../../docker
docker build -t ${APP_NAME}:latest -f Dockerfile ../../..

echo "Step 4: Tagging Docker image..."
docker tag ${APP_NAME}:latest ${ECR_URI}:latest

echo "Step 5: Pushing Docker image to ECR..."
docker push ${ECR_URI}:latest

echo "Step 6: Creating ECS cluster..."
aws ecs describe-clusters --clusters ${CLUSTER_NAME} --region ${REGION} 2>/dev/null || \
    aws ecs create-cluster --cluster-name ${CLUSTER_NAME} --region ${REGION}

echo "Step 7: Registering task definition..."
cat > task-definition.json <<EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "containerDefinitions": [
    {
      "name": "${APP_NAME}",
      "image": "${ECR_URI}:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "ENVIRONMENT",
          "value": "production"
        }
      ],
      "secrets": [
        {
          "name": "ANTHROPIC_API_KEY",
          "valueFrom": "arn:aws:secretsmanager:${REGION}:${AWS_ACCOUNT_ID}:secret:claude/anthropic-api-key"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ],
  "executionRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::${AWS_ACCOUNT_ID}:role/ecsTaskRole"
}
EOF

aws ecs register-task-definition --cli-input-json file://task-definition.json --region ${REGION}

echo "Step 8: Creating or updating ECS service..."
aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${REGION} 2>/dev/null | grep -q "ACTIVE" && {
    echo "Updating existing service..."
    aws ecs update-service \
        --cluster ${CLUSTER_NAME} \
        --service ${SERVICE_NAME} \
        --task-definition ${TASK_FAMILY} \
        --region ${REGION}
} || {
    echo "Creating new service..."
    aws ecs create-service \
        --cluster ${CLUSTER_NAME} \
        --service-name ${SERVICE_NAME} \
        --task-definition ${TASK_FAMILY} \
        --desired-count 2 \
        --launch-type FARGATE \
        --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxx],securityGroups=[sg-xxxxx],assignPublicIp=ENABLED}" \
        --region ${REGION}
}

echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
echo "Cluster: ${CLUSTER_NAME}"
echo "Service: ${SERVICE_NAME}"
echo "ECR Image: ${ECR_URI}:latest"
echo ""
echo "To check service status:"
echo "aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${REGION}"
