#!/bin/bash

# Azure Deployment Script for Claude AI Applications
# This script deploys the application to Azure Container Instances

set -e

# Configuration
APP_NAME="claude-ai-app"
RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-claude-ai-rg}"
LOCATION="${AZURE_LOCATION:-eastus}"
ACR_NAME="${AZURE_ACR_NAME:-claudeairegistry}"
CONTAINER_NAME="${APP_NAME}-container"

echo "=========================================="
echo "Deploying Claude AI Application to Azure"
echo "=========================================="

# Check Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "Error: Azure CLI is not installed. Please install it first."
    exit 1
fi

# Check if logged in to Azure
az account show > /dev/null 2>&1 || {
    echo "Error: Not authenticated with Azure. Please run 'az login'."
    exit 1
}

echo "Using Resource Group: ${RESOURCE_GROUP}"
echo "Using Location: ${LOCATION}"
echo "Using ACR: ${ACR_NAME}"

echo "Step 1: Creating resource group..."
az group create --name ${RESOURCE_GROUP} --location ${LOCATION} || true

echo "Step 2: Creating Azure Container Registry..."
az acr create \
    --resource-group ${RESOURCE_GROUP} \
    --name ${ACR_NAME} \
    --sku Basic \
    --location ${LOCATION} || true

echo "Step 3: Logging in to ACR..."
az acr login --name ${ACR_NAME}

# Get ACR login server
ACR_LOGIN_SERVER=$(az acr show --name ${ACR_NAME} --query loginServer --output tsv)
IMAGE_TAG="${ACR_LOGIN_SERVER}/${APP_NAME}:latest"

echo "Step 4: Building Docker image..."
cd ../../docker
docker build -t ${APP_NAME}:latest -f Dockerfile ../../..

echo "Step 5: Tagging image for ACR..."
docker tag ${APP_NAME}:latest ${IMAGE_TAG}

echo "Step 6: Pushing image to ACR..."
docker push ${IMAGE_TAG}

echo "Step 7: Creating Key Vault for secrets..."
KEYVAULT_NAME="${APP_NAME}-kv-${RANDOM}"
az keyvault create \
    --name ${KEYVAULT_NAME} \
    --resource-group ${RESOURCE_GROUP} \
    --location ${LOCATION} || true

echo "Step 8: Setting Anthropic API Key in Key Vault..."
if [ -z "${ANTHROPIC_API_KEY}" ]; then
    echo "Please enter your Anthropic API key:"
    read -s ANTHROPIC_API_KEY
fi

az keyvault secret set \
    --vault-name ${KEYVAULT_NAME} \
    --name "anthropic-api-key" \
    --value "${ANTHROPIC_API_KEY}"

echo "Step 9: Creating Container Instance..."
az container create \
    --resource-group ${RESOURCE_GROUP} \
    --name ${CONTAINER_NAME} \
    --image ${IMAGE_TAG} \
    --registry-login-server ${ACR_LOGIN_SERVER} \
    --registry-username $(az acr credential show --name ${ACR_NAME} --query username --output tsv) \
    --registry-password $(az acr credential show --name ${ACR_NAME} --query passwords[0].value --output tsv) \
    --dns-name-label ${APP_NAME}-${RANDOM} \
    --ports 8000 \
    --cpu 2 \
    --memory 4 \
    --environment-variables ENVIRONMENT=production \
    --secure-environment-variables ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY} \
    --location ${LOCATION}

# Get the FQDN
FQDN=$(az container show --resource-group ${RESOURCE_GROUP} --name ${CONTAINER_NAME} --query ipAddress.fqdn --output tsv)

echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
echo "Container Instance: ${CONTAINER_NAME}"
echo "FQDN: http://${FQDN}:8000"
echo "Image: ${IMAGE_TAG}"
echo ""
echo "To view logs:"
echo "az container logs --resource-group ${RESOURCE_GROUP} --name ${CONTAINER_NAME}"
echo ""
echo "To delete resources:"
echo "az group delete --name ${RESOURCE_GROUP} --yes --no-wait"
