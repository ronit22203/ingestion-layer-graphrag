"""
Azure configuration for MARA Medical Data Ingestion Pipeline

This module provides utilities for connecting to Azure services when
the pipeline is deployed on Azure.

Usage:
    from infra.azure.config import AzureConfig
    config = AzureConfig()
    client = config.get_blob_client()
"""

import os
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class AzureConfig:
    """
    Configuration for Azure deployment.
    
    Environment variables:
        AZURE_STORAGE_CONNECTION_STRING: Azure Storage connection string
        AZURE_CONTAINER_REGISTRY_URL: Container registry URL
        AZURE_SUBSCRIPTION_ID: Azure subscription ID
        AZURE_RESOURCE_GROUP: Resource group name
        AZURE_STORAGE_ACCOUNT: Storage account name
    """
    
    storage_connection_string: Optional[str] = None
    container_registry_url: Optional[str] = None
    subscription_id: Optional[str] = None
    resource_group: Optional[str] = None
    storage_account: Optional[str] = None
    
    def __post_init__(self):
        """Load configuration from environment variables"""
        self.storage_connection_string = os.getenv(
            "AZURE_STORAGE_CONNECTION_STRING",
            self.storage_connection_string
        )
        self.container_registry_url = os.getenv(
            "AZURE_CONTAINER_REGISTRY_URL",
            self.container_registry_url
        )
        self.subscription_id = os.getenv(
            "AZURE_SUBSCRIPTION_ID",
            self.subscription_id
        )
        self.resource_group = os.getenv(
            "AZURE_RESOURCE_GROUP",
            self.resource_group or "mara-ingestion-prod"
        )
        self.storage_account = os.getenv(
            "AZURE_STORAGE_ACCOUNT",
            self.storage_account or "maraingestionprod"
        )
    
    def is_configured(self) -> bool:
        """Check if Azure is properly configured"""
        return bool(self.storage_connection_string)
    
    def get_blob_client(self):
        """
        Get Azure Blob Storage client
        
        Returns:
            BlobServiceClient: Azure blob client
            
        Raises:
            ValueError: If Azure is not configured
        """
        try:
            from azure.storage.blob import BlobServiceClient
        except ImportError:
            raise ImportError(
                "azure-storage-blob is not installed. "
                "Install with: pip install azure-storage-blob"
            )
        
        if not self.storage_connection_string:
            raise ValueError(
                "AZURE_STORAGE_CONNECTION_STRING not configured"
            )
        
        return BlobServiceClient.from_connection_string(
            self.storage_connection_string
        )
    
    def get_container_client(self, container_name: str):
        """
        Get Azure Blob Storage container client
        
        Args:
            container_name: Name of the container
            
        Returns:
            ContainerClient: Azure container client
        """
        blob_client = self.get_blob_client()
        return blob_client.get_container_client(container_name)
    
    def upload_to_blob(self, container_name: str, blob_name: str, 
                      data: bytes) -> str:
        """
        Upload data to Azure Blob Storage
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            data: Data to upload (bytes)
            
        Returns:
            str: URL of the uploaded blob
        """
        container_client = self.get_container_client(container_name)
        container_client.upload_blob(blob_name, data, overwrite=True)
        
        logger.info(f"Uploaded {blob_name} to {container_name}")
        return f"{self.storage_account}.blob.core.windows.net/{container_name}/{blob_name}"
    
    def download_from_blob(self, container_name: str, 
                          blob_name: str) -> bytes:
        """
        Download data from Azure Blob Storage
        
        Args:
            container_name: Name of the container
            blob_name: Name of the blob
            
        Returns:
            bytes: Downloaded data
        """
        container_client = self.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        logger.info(f"Downloaded {blob_name} from {container_name}")
        return blob_client.download_blob().readall()


def get_azure_config() -> AzureConfig:
    """
    Factory function to get Azure configuration
    
    Returns:
        AzureConfig: Configuration instance
    """
    return AzureConfig()
