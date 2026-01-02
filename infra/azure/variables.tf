variable "resource_group_name" {
  description = "Name of the Azure resource group"
  type        = string
  default     = "mara-ingestion-prod"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "East US"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "storage_account_name" {
  description = "Name of the storage account (must be globally unique, lowercase alphanumeric)"
  type        = string
  default     = "maraingestionprod"
  
  validation {
    condition     = can(regex("^[a-z0-9]{3,24}$", var.storage_account_name))
    error_message = "Storage account name must be 3-24 lowercase alphanumeric characters."
  }
}

variable "cognitive_account_name" {
  description = "Name of the Cognitive Services account"
  type        = string
  default     = "mara-vision-prod"
}

variable "container_registry_name" {
  description = "Name of the Container Registry (must be globally unique, lowercase alphanumeric)"
  type        = string
  default     = "mararegistryprod"
  
  validation {
    condition     = can(regex("^[a-z0-9]{5,50}$", var.container_registry_name))
    error_message = "Registry name must be 5-50 lowercase alphanumeric characters."
  }
}

variable "app_service_plan_name" {
  description = "Name of the App Service Plan"
  type        = string
  default     = "mara-pipeline-plan"
}

variable "app_service_name" {
  description = "Name of the App Service"
  type        = string
  default     = "mara-pipeline-prod"
}
