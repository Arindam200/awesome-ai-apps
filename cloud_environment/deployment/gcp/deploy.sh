#!/bin/bash

# GCP Deployment Script for Claude AI Applications
# This script deploys the application to Google Cloud Run

set -e

# Configuration
APP_NAME="claude-ai-app"
PROJECT_ID="${GCP_PROJECT_ID}"
REGION="${GCP_REGION:-us-central1}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${APP_NAME}"

echo "=========================================="
echo "Deploying Claude AI Application to GCP"
echo "=========================================="

# Check gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
    echo "Error: gcloud CLI is not installed. Please install it first."
    exit 1
fi

# Check if logged in to GCP
gcloud auth print-access-token > /dev/null 2>&1 || {
    echo "Error: Not authenticated with GCP. Please run 'gcloud auth login'."
    exit 1
}

# Check if project ID is set
if [ -z "${PROJECT_ID}" ]; then
    echo "Error: GCP_PROJECT_ID environment variable is not set."
    exit 1
fi

echo "Using Project ID: ${PROJECT_ID}"
echo "Using Region: ${REGION}"

# Set the project
gcloud config set project ${PROJECT_ID}

echo "Step 1: Enabling required APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    containerregistry.googleapis.com \
    secretmanager.googleapis.com

echo "Step 2: Building Docker image with Cloud Build..."
cd ../../docker
gcloud builds submit --tag ${IMAGE_NAME}:latest ../../..

echo "Step 3: Creating secret for Anthropic API Key (if not exists)..."
gcloud secrets describe anthropic-api-key 2>/dev/null || {
    echo "Please enter your Anthropic API key:"
    read -s ANTHROPIC_API_KEY
    echo -n "${ANTHROPIC_API_KEY}" | gcloud secrets create anthropic-api-key \
        --replication-policy="automatic" \
        --data-file=-
}

echo "Step 4: Deploying to Cloud Run..."
gcloud run deploy ${APP_NAME} \
    --image ${IMAGE_NAME}:latest \
    --platform managed \
    --region ${REGION} \
    --allow-unauthenticated \
    --port 8000 \
    --memory 2Gi \
    --cpu 2 \
    --min-instances 0 \
    --max-instances 10 \
    --set-env-vars ENVIRONMENT=production \
    --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
    --timeout 300

# Get the service URL
SERVICE_URL=$(gcloud run services describe ${APP_NAME} --platform managed --region ${REGION} --format 'value(status.url)')

echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
echo "Service URL: ${SERVICE_URL}"
echo "Image: ${IMAGE_NAME}:latest"
echo ""
echo "To view logs:"
echo "gcloud run services logs read ${APP_NAME} --region ${REGION}"
echo ""
echo "To update the service:"
echo "gcloud run services update ${APP_NAME} --region ${REGION}"
