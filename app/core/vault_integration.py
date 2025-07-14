"""
HashiCorp Vault integration for enterprise secrets management

This module provides integration with HashiCorp Vault for centralized
secrets management, dynamic secrets, and advanced security features.
"""

import os
import time
import json
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)

# Optional Vault client import
try:
    import hvac
    VAULT_AVAILABLE = True
except ImportError:
    VAULT_AVAILABLE = False
    logger.warning("HashiCorp Vault client not available. Install 'hvac' package for Vault integration.")


class VaultAuthMethod(str, Enum):
    """Vault authentication methods"""
    TOKEN = "token"
    USERPASS = "userpass"
    APPROLE = "approle"
    KUBERNETES = "kubernetes"
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"


class VaultEngineType(str, Enum):
    """Vault secret engine types"""
    KV_V1 = "kv"
    KV_V2 = "kv-v2"
    DATABASE = "database"
    PKI = "pki"
    TRANSIT = "transit"
    AWS = "aws"
    AZURE = "azure"


@dataclass
class VaultConfig:
    """Configuration for Vault connection"""
    url: str
    auth_method: VaultAuthMethod
    mount_point: str = "secret"
    engine_type: VaultEngineType = VaultEngineType.KV_V2
    namespace: Optional[str] = None
    verify_ssl: bool = True
    timeout: int = 30
    
    # Authentication parameters
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[str] = None
    secret_id: Optional[str] = None
    
    # Advanced settings
    max_retries: int = 3
    retry_delay: float = 1.0
    lease_renewal_threshold: float = 0.8  # Renew when 80% of lease time elapsed


class VaultError(Exception):
    """Exception raised for Vault operations"""
    pass


class VaultClient:
    """HashiCorp Vault client wrapper"""
    
    def __init__(self, config: VaultConfig):
        """
        Initialize Vault client
        
        Args:
            config: Vault configuration
        """
        if not VAULT_AVAILABLE:
            raise VaultError("HashiCorp Vault client not available. Install 'hvac' package.")
        
        self.config = config
        self.client: Optional[hvac.Client] = None
        self._authenticated = False
        self._token_lease_info: Optional[Dict[str, Any]] = None
        
        self._initialize_client()
    
    def _initialize_client(self) -> None:
        """Initialize Vault client connection"""
        try:
            self.client = hvac.Client(
                url=self.config.url,
                verify=self.config.verify_ssl,
                timeout=self.config.timeout,
                namespace=self.config.namespace
            )
            
            # Test connection
            if not self.client.sys.is_initialized():
                raise VaultError("Vault is not initialized")
            
            if self.client.sys.is_sealed():
                raise VaultError("Vault is sealed")
            
            logger.info(
                "Vault client initialized",
                url=self.config.url,
                namespace=self.config.namespace
            )
            
        except Exception as e:
            logger.error("Failed to initialize Vault client", error=str(e))
            raise VaultError(f"Vault initialization failed: {str(e)}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Vault using configured method
        
        Returns:
            bool: True if authentication successful
        """
        if not self.client:
            raise VaultError("Vault client not initialized")
        
        try:
            if self.config.auth_method == VaultAuthMethod.TOKEN:
                return self._authenticate_token()
            elif self.config.auth_method == VaultAuthMethod.USERPASS:
                return self._authenticate_userpass()
            elif self.config.auth_method == VaultAuthMethod.APPROLE:
                return self._authenticate_approle()
            else:
                raise VaultError(f"Unsupported auth method: {self.config.auth_method}")
                
        except Exception as e:
            logger.error("Vault authentication failed", error=str(e))
            self._authenticated = False
            return False
    
    def _authenticate_token(self) -> bool:
        """Authenticate using token"""
        if not self.config.token:
            raise VaultError("Token not provided for token authentication")
        
        self.client.token = self.config.token
        
        # Verify token
        token_info = self.client.auth.token.lookup_self()
        self._token_lease_info = token_info.get('data', {})
        
        self._authenticated = True
        logger.info("Vault token authentication successful")
        return True
    
    def _authenticate_userpass(self) -> bool:
        """Authenticate using username/password"""
        if not self.config.username or not self.config.password:
            raise VaultError("Username/password not provided for userpass authentication")
        
        auth_response = self.client.auth.userpass.login(
            username=self.config.username,
            password=self.config.password
        )
        
        self.client.token = auth_response['auth']['client_token']
        self._token_lease_info = auth_response['auth']
        
        self._authenticated = True
        logger.info("Vault userpass authentication successful")
        return True
    
    def _authenticate_approle(self) -> bool:
        """Authenticate using AppRole"""
        if not self.config.role_id or not self.config.secret_id:
            raise VaultError("Role ID/Secret ID not provided for AppRole authentication")
        
        auth_response = self.client.auth.approle.login(
            role_id=self.config.role_id,
            secret_id=self.config.secret_id
        )
        
        self.client.token = auth_response['auth']['client_token']
        self._token_lease_info = auth_response['auth']
        
        self._authenticated = True
        logger.info("Vault AppRole authentication successful")
        return True
    
    def _ensure_authenticated(self) -> None:
        """Ensure client is authenticated"""
        if not self._authenticated:
            if not self.authenticate():
                raise VaultError("Failed to authenticate with Vault")
        
        # Check token renewal
        if self._token_lease_info and self._should_renew_token():
            self._renew_token()
    
    def _should_renew_token(self) -> bool:
        """Check if token should be renewed"""
        if not self._token_lease_info:
            return False
        
        lease_duration = self._token_lease_info.get('lease_duration', 0)
        if lease_duration == 0:  # Non-expiring token
            return False
        
        # Calculate elapsed time since authentication
        auth_time = self._token_lease_info.get('auth_time', time.time())
        elapsed = time.time() - auth_time
        
        # Renew if we've used more than threshold of lease time
        return elapsed >= (lease_duration * self.config.lease_renewal_threshold)
    
    def _renew_token(self) -> None:
        """Renew authentication token"""
        try:
            if self.config.auth_method == VaultAuthMethod.TOKEN:
                self.client.auth.token.renew_self()
            else:
                # Re-authenticate for other methods
                self.authenticate()
            
            logger.debug("Vault token renewed successfully")
            
        except Exception as e:
            logger.warning("Failed to renew Vault token", error=str(e))
            # Try to re-authenticate
            self._authenticated = False
            self.authenticate()
    
    def read_secret(self, path: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Read secret from Vault
        
        Args:
            path: Secret path
            version: Version for KV v2 (latest if None)
            
        Returns:
            Optional[Dict[str, Any]]: Secret data or None if not found
        """
        self._ensure_authenticated()
        
        try:
            if self.config.engine_type == VaultEngineType.KV_V2:
                response = self.client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.config.mount_point,
                    version=version
                )
                return response['data']['data']
            else:
                response = self.client.secrets.kv.v1.read_secret(
                    path=path,
                    mount_point=self.config.mount_point
                )
                return response['data']
                
        except hvac.exceptions.InvalidPath:
            logger.debug("Secret not found in Vault", path=path)
            return None
        except Exception as e:
            logger.error("Failed to read secret from Vault", path=path, error=str(e))
            raise VaultError(f"Failed to read secret: {str(e)}")
    
    def write_secret(self, path: str, secret_data: Dict[str, Any]) -> bool:
        """
        Write secret to Vault
        
        Args:
            path: Secret path
            secret_data: Secret data to store
            
        Returns:
            bool: True if written successfully
        """
        self._ensure_authenticated()
        
        try:
            if self.config.engine_type == VaultEngineType.KV_V2:
                self.client.secrets.kv.v2.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=self.config.mount_point
                )
            else:
                self.client.secrets.kv.v1.create_or_update_secret(
                    path=path,
                    secret=secret_data,
                    mount_point=self.config.mount_point
                )
            
            logger.info("Secret written to Vault successfully", path=path)
            return True
            
        except Exception as e:
            logger.error("Failed to write secret to Vault", path=path, error=str(e))
            return False
    
    def delete_secret(self, path: str, versions: Optional[List[int]] = None) -> bool:
        """
        Delete secret from Vault
        
        Args:
            path: Secret path
            versions: Versions to delete for KV v2 (all if None)
            
        Returns:
            bool: True if deleted successfully
        """
        self._ensure_authenticated()
        
        try:
            if self.config.engine_type == VaultEngineType.KV_V2:
                if versions:
                    self.client.secrets.kv.v2.delete_secret_versions(
                        path=path,
                        versions=versions,
                        mount_point=self.config.mount_point
                    )
                else:
                    self.client.secrets.kv.v2.delete_metadata_and_all_versions(
                        path=path,
                        mount_point=self.config.mount_point
                    )
            else:
                self.client.secrets.kv.v1.delete_secret(
                    path=path,
                    mount_point=self.config.mount_point
                )
            
            logger.info("Secret deleted from Vault successfully", path=path)
            return True
            
        except Exception as e:
            logger.error("Failed to delete secret from Vault", path=path, error=str(e))
            return False
    
    def list_secrets(self, path: str = "") -> List[str]:
        """
        List secrets at path
        
        Args:
            path: Path to list
            
        Returns:
            List[str]: List of secret names
        """
        self._ensure_authenticated()
        
        try:
            if self.config.engine_type == VaultEngineType.KV_V2:
                response = self.client.secrets.kv.v2.list_secrets(
                    path=path,
                    mount_point=self.config.mount_point
                )
            else:
                response = self.client.secrets.kv.v1.list_secrets(
                    path=path,
                    mount_point=self.config.mount_point
                )
            
            return response['data']['keys']
            
        except hvac.exceptions.InvalidPath:
            return []
        except Exception as e:
            logger.error("Failed to list secrets from Vault", path=path, error=str(e))
            return []
    
    def encrypt_data(self, plaintext: str, key_name: str) -> Optional[str]:
        """
        Encrypt data using Vault Transit engine
        
        Args:
            plaintext: Data to encrypt
            key_name: Transit key name
            
        Returns:
            Optional[str]: Encrypted data or None if failed
        """
        self._ensure_authenticated()
        
        try:
            import base64
            
            # Encode plaintext
            encoded_plaintext = base64.b64encode(plaintext.encode()).decode()
            
            response = self.client.secrets.transit.encrypt_data(
                name=key_name,
                plaintext=encoded_plaintext
            )
            
            return response['data']['ciphertext']
            
        except Exception as e:
            logger.error("Failed to encrypt data with Vault", error=str(e))
            return None
    
    def decrypt_data(self, ciphertext: str, key_name: str) -> Optional[str]:
        """
        Decrypt data using Vault Transit engine
        
        Args:
            ciphertext: Encrypted data
            key_name: Transit key name
            
        Returns:
            Optional[str]: Decrypted data or None if failed
        """
        self._ensure_authenticated()
        
        try:
            import base64
            
            response = self.client.secrets.transit.decrypt_data(
                name=key_name,
                ciphertext=ciphertext
            )
            
            # Decode plaintext
            decoded_plaintext = base64.b64decode(response['data']['plaintext']).decode()
            
            return decoded_plaintext
            
        except Exception as e:
            logger.error("Failed to decrypt data with Vault", error=str(e))
            return None


class VaultSecretsManager:
    """Vault-backed secrets manager"""
    
    def __init__(self, vault_client: Optional[VaultClient] = None):
        """
        Initialize Vault secrets manager
        
        Args:
            vault_client: Vault client instance
        """
        self.vault_client = vault_client
        self._fallback_enabled = True
    
    @classmethod
    def from_config(cls, config: VaultConfig) -> 'VaultSecretsManager':
        """
        Create manager from configuration
        
        Args:
            config: Vault configuration
            
        Returns:
            VaultSecretsManager: Manager instance
        """
        if not VAULT_AVAILABLE:
            logger.warning("Vault not available, creating manager without Vault client")
            return cls(None)
        
        try:
            vault_client = VaultClient(config)
            vault_client.authenticate()
            return cls(vault_client)
        except Exception as e:
            logger.error("Failed to create Vault client", error=str(e))
            return cls(None)
    
    @classmethod
    def from_environment(cls) -> 'VaultSecretsManager':
        """
        Create manager from environment variables
        
        Returns:
            VaultSecretsManager: Manager instance
        """
        vault_url = os.getenv('VAULT_ADDR')
        if not vault_url:
            logger.info("VAULT_ADDR not set, creating manager without Vault")
            return cls(None)
        
        # Determine auth method
        if os.getenv('VAULT_TOKEN'):
            auth_method = VaultAuthMethod.TOKEN
            token = os.getenv('VAULT_TOKEN')
            config = VaultConfig(
                url=vault_url,
                auth_method=auth_method,
                token=token,
                namespace=os.getenv('VAULT_NAMESPACE')
            )
        elif os.getenv('VAULT_USERNAME') and os.getenv('VAULT_PASSWORD'):
            auth_method = VaultAuthMethod.USERPASS
            config = VaultConfig(
                url=vault_url,
                auth_method=auth_method,
                username=os.getenv('VAULT_USERNAME'),
                password=os.getenv('VAULT_PASSWORD'),
                namespace=os.getenv('VAULT_NAMESPACE')
            )
        elif os.getenv('VAULT_ROLE_ID') and os.getenv('VAULT_SECRET_ID'):
            auth_method = VaultAuthMethod.APPROLE
            config = VaultConfig(
                url=vault_url,
                auth_method=auth_method,
                role_id=os.getenv('VAULT_ROLE_ID'),
                secret_id=os.getenv('VAULT_SECRET_ID'),
                namespace=os.getenv('VAULT_NAMESPACE')
            )
        else:
            logger.warning("No Vault authentication credentials found in environment")
            return cls(None)
        
        return cls.from_config(config)
    
    def get_secret(self, path: str, key: Optional[str] = None) -> Optional[str]:
        """
        Get secret from Vault
        
        Args:
            path: Secret path
            key: Specific key within secret (returns whole secret if None)
            
        Returns:
            Optional[str]: Secret value or None if not found
        """
        if not self.vault_client:
            if self._fallback_enabled:
                # Fallback to environment variable
                env_var = path.replace('/', '_').upper()
                return os.getenv(env_var)
            return None
        
        try:
            secret_data = self.vault_client.read_secret(path)
            if not secret_data:
                return None
            
            if key:
                return secret_data.get(key)
            else:
                # Return JSON string of entire secret
                return json.dumps(secret_data)
                
        except Exception as e:
            logger.error("Failed to get secret from Vault", path=path, error=str(e))
            return None
    
    def set_secret(self, path: str, secret_data: Union[str, Dict[str, Any]]) -> bool:
        """
        Set secret in Vault
        
        Args:
            path: Secret path
            secret_data: Secret data (string or dict)
            
        Returns:
            bool: True if set successfully
        """
        if not self.vault_client:
            logger.warning("Vault client not available, cannot set secret")
            return False
        
        try:
            if isinstance(secret_data, str):
                data = {'value': secret_data}
            else:
                data = secret_data
            
            return self.vault_client.write_secret(path, data)
            
        except Exception as e:
            logger.error("Failed to set secret in Vault", path=path, error=str(e))
            return False


# Global Vault secrets manager
vault_secrets_manager = VaultSecretsManager.from_environment()

# Convenience functions
def get_vault_secret(path: str, key: Optional[str] = None) -> Optional[str]:
    """Get secret from Vault using global manager"""
    return vault_secrets_manager.get_secret(path, key)

def set_vault_secret(path: str, secret_data: Union[str, Dict[str, Any]]) -> bool:
    """Set secret in Vault using global manager"""
    return vault_secrets_manager.set_secret(path, secret_data)


# Export main classes and functions
__all__ = [
    'VaultAuthMethod',
    'VaultEngineType',
    'VaultConfig',
    'VaultError',
    'VaultClient',
    'VaultSecretsManager',
    'get_vault_secret',
    'set_vault_secret',
    'vault_secrets_manager'
]
