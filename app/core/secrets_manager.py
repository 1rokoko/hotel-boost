"""
Comprehensive secrets management system with encryption at rest

This module provides secure storage and management of application secrets
including API keys, database credentials, and other sensitive configuration.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List, Set, Union
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import structlog

from app.utils.encryption import SecureEncryption, KeyManager, EncryptionError
from app.core.config import settings

logger = structlog.get_logger(__name__)


class SecretType(str, Enum):
    """Types of secrets managed by the system"""
    API_KEY = "api_key"
    DATABASE_CREDENTIAL = "database_credential"
    JWT_SECRET = "jwt_secret"
    WEBHOOK_TOKEN = "webhook_token"
    ENCRYPTION_KEY = "encryption_key"
    OAUTH_SECRET = "oauth_secret"
    CERTIFICATE = "certificate"
    PASSWORD = "password"
    GENERIC = "generic"


class SecretScope(str, Enum):
    """Scope of secret access"""
    GLOBAL = "global"
    HOTEL = "hotel"
    USER = "user"
    SERVICE = "service"


@dataclass
class SecretMetadata:
    """Metadata for stored secrets"""
    secret_id: str
    secret_type: SecretType
    scope: SecretScope
    created_at: float
    updated_at: float
    expires_at: Optional[float] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    rotation_interval: Optional[int] = None  # seconds
    last_accessed: Optional[float] = None
    access_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SecretMetadata':
        """Create from dictionary"""
        return cls(**data)


class SecretStore:
    """Secure secret storage with encryption at rest"""
    
    def __init__(
        self,
        storage_path: Optional[str] = None,
        key_manager: Optional[KeyManager] = None
    ):
        """
        Initialize secret store
        
        Args:
            storage_path: Path to secrets storage directory
            key_manager: Key manager instance
        """
        self.storage_path = Path(storage_path or settings.SECRETS_STORAGE_PATH or ".secrets")
        self.key_manager = key_manager or KeyManager()
        self.encryption = self.key_manager.get_encryption()
        
        # Ensure storage directory exists with secure permissions
        self.storage_path.mkdir(mode=0o700, parents=True, exist_ok=True)
        
        # Metadata cache
        self._metadata_cache: Dict[str, SecretMetadata] = {}
        self._cache_loaded = False
        
        logger.info(
            "Secret store initialized",
            storage_path=str(self.storage_path),
            cache_size=len(self._metadata_cache)
        )
    
    def _load_metadata_cache(self) -> None:
        """Load metadata cache from storage"""
        if self._cache_loaded:
            return
        
        try:
            metadata_file = self.storage_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata_data = json.load(f)
                
                for secret_id, meta_dict in metadata_data.items():
                    self._metadata_cache[secret_id] = SecretMetadata.from_dict(meta_dict)
                
                logger.debug(
                    "Metadata cache loaded",
                    secret_count=len(self._metadata_cache)
                )
            
            self._cache_loaded = True
            
        except Exception as e:
            logger.error("Failed to load metadata cache", error=str(e))
            self._metadata_cache = {}
            self._cache_loaded = True
    
    def _save_metadata_cache(self) -> None:
        """Save metadata cache to storage"""
        try:
            metadata_file = self.storage_path / "metadata.json"
            metadata_data = {
                secret_id: meta.to_dict()
                for secret_id, meta in self._metadata_cache.items()
            }
            
            # Write to temporary file first, then rename (atomic operation)
            temp_file = metadata_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(metadata_data, f, indent=2)
            
            temp_file.replace(metadata_file)
            
            logger.debug("Metadata cache saved")
            
        except Exception as e:
            logger.error("Failed to save metadata cache", error=str(e))
    
    def store_secret(
        self,
        secret_id: str,
        secret_value: str,
        secret_type: SecretType = SecretType.GENERIC,
        scope: SecretScope = SecretScope.GLOBAL,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        expires_at: Optional[float] = None,
        rotation_interval: Optional[int] = None
    ) -> bool:
        """
        Store encrypted secret
        
        Args:
            secret_id: Unique identifier for secret
            secret_value: Secret value to encrypt and store
            secret_type: Type of secret
            scope: Access scope
            description: Optional description
            tags: Optional tags for categorization
            expires_at: Optional expiration timestamp
            rotation_interval: Optional rotation interval in seconds
            
        Returns:
            bool: True if stored successfully
        """
        self._load_metadata_cache()
        
        try:
            # Encrypt secret value
            encrypted_value = self.encryption.encrypt_string(secret_value)
            
            # Create metadata
            current_time = time.time()
            metadata = SecretMetadata(
                secret_id=secret_id,
                secret_type=secret_type,
                scope=scope,
                created_at=current_time,
                updated_at=current_time,
                expires_at=expires_at,
                description=description,
                tags=tags or [],
                rotation_interval=rotation_interval
            )
            
            # Store encrypted secret
            secret_file = self.storage_path / f"{secret_id}.enc"
            with open(secret_file, 'w') as f:
                f.write(encrypted_value)
            
            # Set secure file permissions
            secret_file.chmod(0o600)
            
            # Update metadata cache
            self._metadata_cache[secret_id] = metadata
            self._save_metadata_cache()
            
            logger.info(
                "Secret stored successfully",
                secret_id=secret_id,
                secret_type=secret_type.value,
                scope=scope.value
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to store secret",
                secret_id=secret_id,
                error=str(e)
            )
            return False
    
    def retrieve_secret(self, secret_id: str) -> Optional[str]:
        """
        Retrieve and decrypt secret
        
        Args:
            secret_id: Secret identifier
            
        Returns:
            Optional[str]: Decrypted secret value or None if not found
        """
        self._load_metadata_cache()
        
        try:
            # Check if secret exists in metadata
            if secret_id not in self._metadata_cache:
                logger.warning("Secret not found in metadata", secret_id=secret_id)
                return None
            
            metadata = self._metadata_cache[secret_id]
            
            # Check expiration
            if metadata.expires_at and time.time() > metadata.expires_at:
                logger.warning("Secret has expired", secret_id=secret_id)
                return None
            
            # Read encrypted secret
            secret_file = self.storage_path / f"{secret_id}.enc"
            if not secret_file.exists():
                logger.error("Secret file not found", secret_id=secret_id)
                return None
            
            with open(secret_file, 'r') as f:
                encrypted_value = f.read()
            
            # Decrypt secret
            secret_value = self.encryption.decrypt_string(encrypted_value)
            
            # Update access metadata
            metadata.last_accessed = time.time()
            metadata.access_count += 1
            self._save_metadata_cache()
            
            logger.debug(
                "Secret retrieved successfully",
                secret_id=secret_id,
                access_count=metadata.access_count
            )
            
            return secret_value
            
        except EncryptionError as e:
            logger.error(
                "Failed to decrypt secret",
                secret_id=secret_id,
                error=str(e)
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to retrieve secret",
                secret_id=secret_id,
                error=str(e)
            )
            return None
    
    def delete_secret(self, secret_id: str) -> bool:
        """
        Delete secret and its metadata
        
        Args:
            secret_id: Secret identifier
            
        Returns:
            bool: True if deleted successfully
        """
        self._load_metadata_cache()
        
        try:
            # Remove from metadata cache
            if secret_id in self._metadata_cache:
                del self._metadata_cache[secret_id]
                self._save_metadata_cache()
            
            # Remove secret file
            secret_file = self.storage_path / f"{secret_id}.enc"
            if secret_file.exists():
                secret_file.unlink()
            
            logger.info("Secret deleted successfully", secret_id=secret_id)
            return True
            
        except Exception as e:
            logger.error(
                "Failed to delete secret",
                secret_id=secret_id,
                error=str(e)
            )
            return False
    
    def list_secrets(
        self,
        secret_type: Optional[SecretType] = None,
        scope: Optional[SecretScope] = None,
        tags: Optional[List[str]] = None
    ) -> List[SecretMetadata]:
        """
        List secrets with optional filtering
        
        Args:
            secret_type: Filter by secret type
            scope: Filter by scope
            tags: Filter by tags (must have all specified tags)
            
        Returns:
            List[SecretMetadata]: List of matching secret metadata
        """
        self._load_metadata_cache()
        
        results = []
        
        for metadata in self._metadata_cache.values():
            # Filter by type
            if secret_type and metadata.secret_type != secret_type:
                continue
            
            # Filter by scope
            if scope and metadata.scope != scope:
                continue
            
            # Filter by tags
            if tags:
                if not metadata.tags or not all(tag in metadata.tags for tag in tags):
                    continue
            
            # Check expiration
            if metadata.expires_at and time.time() > metadata.expires_at:
                continue
            
            results.append(metadata)
        
        return results
    
    def rotate_secret(self, secret_id: str, new_value: str) -> bool:
        """
        Rotate secret with new value
        
        Args:
            secret_id: Secret identifier
            new_value: New secret value
            
        Returns:
            bool: True if rotated successfully
        """
        self._load_metadata_cache()
        
        if secret_id not in self._metadata_cache:
            logger.error("Cannot rotate non-existent secret", secret_id=secret_id)
            return False
        
        try:
            metadata = self._metadata_cache[secret_id]
            
            # Store new value
            success = self.store_secret(
                secret_id=secret_id,
                secret_value=new_value,
                secret_type=metadata.secret_type,
                scope=metadata.scope,
                description=metadata.description,
                tags=metadata.tags,
                expires_at=metadata.expires_at,
                rotation_interval=metadata.rotation_interval
            )
            
            if success:
                logger.info("Secret rotated successfully", secret_id=secret_id)
            
            return success
            
        except Exception as e:
            logger.error(
                "Failed to rotate secret",
                secret_id=secret_id,
                error=str(e)
            )
            return False
    
    def check_rotation_needed(self) -> List[str]:
        """
        Check which secrets need rotation
        
        Returns:
            List[str]: List of secret IDs that need rotation
        """
        self._load_metadata_cache()
        
        current_time = time.time()
        rotation_needed = []
        
        for secret_id, metadata in self._metadata_cache.items():
            if metadata.rotation_interval:
                next_rotation = metadata.updated_at + metadata.rotation_interval
                if current_time >= next_rotation:
                    rotation_needed.append(secret_id)
        
        return rotation_needed
    
    def get_secret_metadata(self, secret_id: str) -> Optional[SecretMetadata]:
        """
        Get metadata for secret
        
        Args:
            secret_id: Secret identifier
            
        Returns:
            Optional[SecretMetadata]: Secret metadata or None if not found
        """
        self._load_metadata_cache()
        return self._metadata_cache.get(secret_id)
    
    def export_secrets(
        self,
        export_path: str,
        include_values: bool = False,
        secret_ids: Optional[List[str]] = None
    ) -> bool:
        """
        Export secrets metadata and optionally values
        
        Args:
            export_path: Path to export file
            include_values: Whether to include decrypted values
            secret_ids: Specific secrets to export (all if None)
            
        Returns:
            bool: True if exported successfully
        """
        self._load_metadata_cache()
        
        try:
            export_data = {
                'exported_at': time.time(),
                'include_values': include_values,
                'secrets': {}
            }
            
            secrets_to_export = secret_ids or list(self._metadata_cache.keys())
            
            for secret_id in secrets_to_export:
                if secret_id not in self._metadata_cache:
                    continue
                
                metadata = self._metadata_cache[secret_id]
                secret_data = {
                    'metadata': metadata.to_dict()
                }
                
                if include_values:
                    secret_value = self.retrieve_secret(secret_id)
                    if secret_value:
                        secret_data['value'] = secret_value
                
                export_data['secrets'][secret_id] = secret_data
            
            with open(export_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(
                "Secrets exported successfully",
                export_path=export_path,
                secret_count=len(export_data['secrets']),
                include_values=include_values
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to export secrets", error=str(e))
            return False


class SecretsManager:
    """High-level secrets management interface"""
    
    def __init__(self, secret_store: Optional[SecretStore] = None):
        """
        Initialize secrets manager
        
        Args:
            secret_store: Secret store instance
        """
        self.store = secret_store or SecretStore()
        self._env_secrets_cache: Dict[str, str] = {}
    
    def get_secret(
        self,
        secret_id: str,
        default: Optional[str] = None,
        fallback_to_env: bool = True
    ) -> Optional[str]:
        """
        Get secret with fallback to environment variables
        
        Args:
            secret_id: Secret identifier
            default: Default value if secret not found
            fallback_to_env: Whether to fallback to environment variables
            
        Returns:
            Optional[str]: Secret value or default
        """
        # Try to get from secure store first
        secret_value = self.store.retrieve_secret(secret_id)
        
        if secret_value is not None:
            return secret_value
        
        # Fallback to environment variable
        if fallback_to_env:
            env_var = secret_id.upper()
            env_value = os.getenv(env_var)
            
            if env_value:
                logger.debug(
                    "Secret retrieved from environment",
                    secret_id=secret_id,
                    env_var=env_var
                )
                return env_value
        
        # Return default
        if default is not None:
            logger.debug(
                "Using default value for secret",
                secret_id=secret_id
            )
            return default
        
        logger.warning("Secret not found", secret_id=secret_id)
        return None
    
    def set_secret(
        self,
        secret_id: str,
        secret_value: str,
        secret_type: SecretType = SecretType.GENERIC,
        **kwargs
    ) -> bool:
        """
        Set secret in secure store
        
        Args:
            secret_id: Secret identifier
            secret_value: Secret value
            secret_type: Type of secret
            **kwargs: Additional metadata
            
        Returns:
            bool: True if stored successfully
        """
        return self.store.store_secret(
            secret_id=secret_id,
            secret_value=secret_value,
            secret_type=secret_type,
            **kwargs
        )
    
    def migrate_env_secrets(self, secret_mapping: Dict[str, SecretType]) -> int:
        """
        Migrate secrets from environment variables to secure store
        
        Args:
            secret_mapping: Mapping of env var names to secret types
            
        Returns:
            int: Number of secrets migrated
        """
        migrated_count = 0
        
        for env_var, secret_type in secret_mapping.items():
            env_value = os.getenv(env_var)
            if env_value:
                secret_id = env_var.lower()
                
                success = self.store.store_secret(
                    secret_id=secret_id,
                    secret_value=env_value,
                    secret_type=secret_type,
                    description=f"Migrated from environment variable {env_var}"
                )
                
                if success:
                    migrated_count += 1
                    logger.info(
                        "Secret migrated from environment",
                        env_var=env_var,
                        secret_id=secret_id
                    )
        
        logger.info(
            "Environment secrets migration completed",
            migrated_count=migrated_count,
            total_mapping=len(secret_mapping)
        )
        
        return migrated_count


# Global secrets manager instance
secrets_manager = SecretsManager()

# Convenience functions
def get_secret(secret_id: str, default: Optional[str] = None) -> Optional[str]:
    """Get secret using global manager"""
    return secrets_manager.get_secret(secret_id, default)

def set_secret(secret_id: str, secret_value: str, secret_type: SecretType = SecretType.GENERIC) -> bool:
    """Set secret using global manager"""
    return secrets_manager.set_secret(secret_id, secret_value, secret_type)


# Export main classes and functions
__all__ = [
    'SecretType',
    'SecretScope',
    'SecretMetadata',
    'SecretStore',
    'SecretsManager',
    'get_secret',
    'set_secret',
    'secrets_manager'
]
