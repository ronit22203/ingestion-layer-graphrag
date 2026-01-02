terraform {
  required_version = ">= 1.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }

  # Uncomment to use remote state in Azure Storage
  # backend "azurerm" {
  #   resource_group_name  = "my-rg"
  #   storage_account_name = "mystorageaccount"
  #   container_name       = "tfstate"
  #   key                  = "prod.tfstate"
  # }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "main" {
  name     = var.resource_group_name
  location = var.location

  tags = {
    Environment = var.environment
    Project     = "mara-ingestion"
  }
}

# Storage Account for documents and outputs
resource "azurerm_storage_account" "docs" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "GRS"

  tags = {
    Environment = var.environment
    Purpose     = "document-storage"
  }
}

# Blob Storage Containers
resource "azurerm_storage_container" "raw_pdfs" {
  name                  = "raw-pdfs"
  storage_account_name  = azurerm_storage_account.docs.name
  container_access_type = "private"
}

resource "azurerm_storage_container" "processed_data" {
  name                  = "processed-data"
  storage_account_name  = azurerm_storage_account.docs.name
  container_access_type = "private"
}

# Cognitive Services (for future OCR enhancement)
resource "azurerm_cognitive_account" "ocr" {
  name                = var.cognitive_account_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  kind                = "ComputerVision"
  sku_name            = "S1"

  tags = {
    Environment = var.environment
    Purpose     = "document-ocr"
  }
}

# Container Registry (for Docker images)
resource "azurerm_container_registry" "acr" {
  name                = var.container_registry_name
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Basic"
  admin_enabled       = true

  tags = {
    Environment = var.environment
  }
}

# App Service Plan (for running the pipeline)
resource "azurerm_service_plan" "app_service" {
  name                = var.app_service_plan_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  os_type             = "Linux"
  sku_name            = "B2"

  tags = {
    Environment = var.environment
  }
}

# App Service (Web app to host pipeline)
resource "azurerm_linux_web_app" "pipeline" {
  name                = var.app_service_name
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  service_plan_id     = azurerm_service_plan.app_service.id

  site_config {
    container_registry_use_managed_identity = true
  }

  identity {
    type = "SystemAssigned"
  }

  tags = {
    Environment = var.environment
  }
}

# Outputs
output "storage_account_id" {
  value = azurerm_storage_account.docs.id
}

output "container_registry_login_server" {
  value = azurerm_container_registry.acr.login_server
}

output "app_service_url" {
  value = azurerm_linux_web_app.pipeline.default_hostname
}
