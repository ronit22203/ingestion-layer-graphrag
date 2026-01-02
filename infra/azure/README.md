# Azure Deployment Configuration for MARA Ingestion Pipeline

This directory contains infrastructure-as-code and configuration for deploying the MARA Medical Data Ingestion Pipeline to Azure.

## Files

- **main.tf** - Terraform configuration for Azure resources (Storage, ACR, App Service, Cognitive Services)
- **variables.tf** - Terraform input variables with defaults
- **config.py** - Python module for Azure runtime configuration and client utilities
- **terraform.tfvars.example** - Example Terraform variables file

## Prerequisites

- Azure CLI installed: `brew install azure-cli` (macOS) or `choco install azure-cli` (Windows)
- Terraform >= 1.0: `brew install terraform`
- Azure subscription with appropriate permissions

## Setup

### 1. Authenticate with Azure

```bash
az login
```

### 2. Create Terraform Variables File

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your Azure details
```

### 3. Initialize Terraform

```bash
terraform init
```

### 4. Plan Infrastructure

```bash
terraform plan -out=tfplan
```

### 5. Apply Infrastructure

```bash
terraform apply tfplan
```

## Azure Resources Created

- **Resource Group**: Logical container for all resources
- **Storage Account**: Blob storage for PDFs and processed data
  - Containers: `raw-pdfs`, `processed-data`
- **Container Registry**: Private Docker registry for pipeline images
- **Cognitive Services**: Computer Vision API for OCR enhancement
- **App Service**: Linux web app to run the ingestion pipeline
- **App Service Plan**: Compute plan for the App Service

## Runtime Configuration

When deploying to Azure, set these environment variables:

```bash
AZURE_STORAGE_CONNECTION_STRING=<connection-string>
AZURE_CONTAINER_REGISTRY_URL=<registry-url>
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=mara-ingestion-prod
AZURE_STORAGE_ACCOUNT=maraingestionprod
```

### Using in Python

```python
from infra.azure.config import get_azure_config

config = get_azure_config()
blob_client = config.get_blob_client()

# Upload files
config.upload_to_blob("raw-pdfs", "document.pdf", pdf_bytes)

# Download files
data = config.download_from_blob("processed-data", "chunks.json")
```

## Deployment Options

### Option 1: Azure Container Instances (ACI)

For one-off runs:

```bash
az container create \
  --resource-group mara-ingestion-prod \
  --name mara-pipeline \
  --image mararegistryprod.azurecr.io/mara-pipeline:latest \
  --environment-variables \
    AZURE_STORAGE_CONNECTION_STRING=$CONNECTION_STRING
```

### Option 2: Azure Container Apps

For scalable, managed containerization:

```bash
az containerapp create \
  --resource-group mara-ingestion-prod \
  --name mara-pipeline \
  --image mararegistryprod.azurecr.io/mara-pipeline:latest
```

### Option 3: Azure Functions (Serverless)

For scheduled or event-driven runs:

```bash
func azure functionapp create \
  --resource-group mara-ingestion-prod \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11
```

## Cost Optimization

- Use **Spot Instances** for non-critical workloads
- **Autoscaling**: Configure based on document volume
- **Storage Tiering**: Move old data to cool/archive tier
- **Cognitive Services**: S1 tier sufficient for most use cases

## Monitoring

### View Logs

```bash
az webapp log tail \
  --resource-group mara-ingestion-prod \
  --name mara-pipeline-prod
```

### Monitor Resources

```bash
az resource list \
  --resource-group mara-ingestion-prod \
  --output table
```

## Cleanup

```bash
terraform destroy
```

## Troubleshooting

### Connection String Issues

```bash
az storage account show-connection-string \
  --name maraingestionprod \
  --resource-group mara-ingestion-prod
```

### Registry Login Issues

```bash
az acr login --name mararegistryprod
```

### View Detailed Logs

```bash
az container logs --resource-group mara-ingestion-prod --name mara-pipeline
```

## Further Reading

- [Azure Storage Documentation](https://learn.microsoft.com/en-us/azure/storage/)
- [Terraform Azure Provider](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs)
- [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/)
- [Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/)
