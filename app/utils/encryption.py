"""
Encryption utilities for secure key derivation and storage

This module provides cryptographic utilities for encrypting secrets at rest,
key derivation, and secure storage of sensitive data.
"""

import os
import base64
import hashlib
import secrets
from typing import Optional, Tuple, Dict, Any, Union
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import structlog

logger = structlog.get_logger(__name__)


class EncryptionError(Exception):
    """Exception raised when encryption operations fail"""
    pass


class KeyDerivationError(Exception):
    """Exception raised when key derivation fails"""
    pass


class SecureEncryption:
    """Secure encryption utility with multiple algorithms"""
    
    def __init__(self, master_key: Optional[bytes] = None):
        """
        Initialize encryption utility
        
        Args:
            master_key: Master key for encryption (generated if None)
        """
        self.backend = default_backend()
        self._master_key = master_key or self._generate_master_key()
        self._fernet = None
    
    def _generate_master_key(self) -> bytes:
        """Generate a secure master key"""
        return secrets.token_bytes(32)  # 256-bit key
    
    def get_fernet_key(self, salt: Optional[bytes] = None) -> Fernet:
        """
        Get Fernet encryption instance with derived key
        
        Args:
            salt: Salt for key derivation (generated if None)
            
        Returns:
            Fernet: Encryption instance
        """
        if salt is None:
            salt = secrets.token_bytes(16)
        
        # Derive key using PBKDF2
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=self.backend
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(self._master_key))
        return Fernet(key)
    
    def encrypt_data(
        self,
        data: Union[str, bytes],
        use_fernet: bool = True
    ) -> Tuple[bytes, bytes]:
        """
        Encrypt data with salt
        
        Args:
            data: Data to encrypt
            use_fernet: Use Fernet encryption (recommended)
            
        Returns:
            Tuple of (encrypted_data, salt)
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        
        try:
            salt = secrets.token_bytes(16)
            
            if use_fernet:
                fernet = self.get_fernet_key(salt)
                encrypted_data = fernet.encrypt(data)
            else:
                # Use AES-GCM for larger data
                encrypted_data = self._encrypt_aes_gcm(data, salt)
            
            logger.debug(
                "Data encrypted successfully",
                data_size=len(data),
                encrypted_size=len(encrypted_data),
                algorithm="fernet" if use_fernet else "aes-gcm"
            )
            
            return encrypted_data, salt
            
        except Exception as e:
            logger.error("Encryption failed", error=str(e))
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
    
    def decrypt_data(
        self,
        encrypted_data: bytes,
        salt: bytes,
        use_fernet: bool = True
    ) -> bytes:
        """
        Decrypt data with salt
        
        Args:
            encrypted_data: Encrypted data
            salt: Salt used for encryption
            use_fernet: Use Fernet decryption
            
        Returns:
            bytes: Decrypted data
        """
        try:
            if use_fernet:
                fernet = self.get_fernet_key(salt)
                decrypted_data = fernet.decrypt(encrypted_data)
            else:
                # Use AES-GCM for larger data
                decrypted_data = self._decrypt_aes_gcm(encrypted_data, salt)
            
            logger.debug(
                "Data decrypted successfully",
                encrypted_size=len(encrypted_data),
                decrypted_size=len(decrypted_data),
                algorithm="fernet" if use_fernet else "aes-gcm"
            )
            
            return decrypted_data
            
        except Exception as e:
            logger.error("Decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt data: {str(e)}")
    
    def _encrypt_aes_gcm(self, data: bytes, salt: bytes) -> bytes:
        """Encrypt data using AES-GCM"""
        # Derive key using Scrypt (more secure for larger data)
        kdf = Scrypt(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            backend=self.backend
        )
        key = kdf.derive(self._master_key)
        
        # Generate IV
        iv = secrets.token_bytes(12)  # 96-bit IV for GCM
        
        # Encrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        
        # Combine IV, tag, and ciphertext
        return iv + encryptor.tag + ciphertext
    
    def _decrypt_aes_gcm(self, encrypted_data: bytes, salt: bytes) -> bytes:
        """Decrypt data using AES-GCM"""
        # Derive key
        kdf = Scrypt(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            backend=self.backend
        )
        key = kdf.derive(self._master_key)
        
        # Extract IV, tag, and ciphertext
        iv = encrypted_data[:12]
        tag = encrypted_data[12:28]
        ciphertext = encrypted_data[28:]
        
        # Decrypt
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def encrypt_string(self, text: str) -> str:
        """
        Encrypt string and return base64-encoded result
        
        Args:
            text: Text to encrypt
            
        Returns:
            str: Base64-encoded encrypted data with salt
        """
        encrypted_data, salt = self.encrypt_data(text)
        
        # Combine salt and encrypted data
        combined = salt + encrypted_data
        
        # Return base64-encoded result
        return base64.b64encode(combined).decode('utf-8')
    
    def decrypt_string(self, encrypted_text: str) -> str:
        """
        Decrypt base64-encoded encrypted string
        
        Args:
            encrypted_text: Base64-encoded encrypted text
            
        Returns:
            str: Decrypted text
        """
        try:
            # Decode base64
            combined = base64.b64decode(encrypted_text.encode('utf-8'))
            
            # Extract salt and encrypted data
            salt = combined[:16]
            encrypted_data = combined[16:]
            
            # Decrypt
            decrypted_data = self.decrypt_data(encrypted_data, salt)
            
            return decrypted_data.decode('utf-8')
            
        except Exception as e:
            logger.error("String decryption failed", error=str(e))
            raise EncryptionError(f"Failed to decrypt string: {str(e)}")
    
    def generate_key_pair(self) -> Tuple[bytes, bytes]:
        """
        Generate RSA key pair for asymmetric encryption
        
        Returns:
            Tuple of (private_key_pem, public_key_pem)
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import rsa
            
            # Generate private key
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=self.backend
            )
            
            # Serialize private key
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            # Serialize public key
            public_key = private_key.public_key()
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            logger.info("RSA key pair generated successfully")
            
            return private_pem, public_pem
            
        except Exception as e:
            logger.error("Key pair generation failed", error=str(e))
            raise EncryptionError(f"Failed to generate key pair: {str(e)}")
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> Tuple[str, bytes]:
        """
        Hash password using Scrypt
        
        Args:
            password: Password to hash
            salt: Salt for hashing (generated if None)
            
        Returns:
            Tuple of (hashed_password_hex, salt)
        """
        if salt is None:
            salt = secrets.token_bytes(32)
        
        try:
            kdf = Scrypt(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                n=2**14,
                r=8,
                p=1,
                backend=self.backend
            )
            
            key = kdf.derive(password.encode('utf-8'))
            hashed_password = key.hex()
            
            logger.debug("Password hashed successfully")
            
            return hashed_password, salt
            
        except Exception as e:
            logger.error("Password hashing failed", error=str(e))
            raise EncryptionError(f"Failed to hash password: {str(e)}")
    
    def verify_password(self, password: str, hashed_password: str, salt: bytes) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Password to verify
            hashed_password: Hashed password (hex)
            salt: Salt used for hashing
            
        Returns:
            bool: True if password is correct
        """
        try:
            # Hash the provided password
            new_hash, _ = self.hash_password(password, salt)
            
            # Compare hashes using constant-time comparison
            import hmac
            return hmac.compare_digest(hashed_password, new_hash)
            
        except Exception as e:
            logger.error("Password verification failed", error=str(e))
            return False


class KeyManager:
    """Secure key management utility"""
    
    def __init__(self, key_file: Optional[str] = None):
        """
        Initialize key manager
        
        Args:
            key_file: Path to key file (uses environment if None)
        """
        self.key_file = key_file or os.getenv('ENCRYPTION_KEY_FILE', '.encryption_key')
        self._master_key = None
        self.encryption = None
    
    def load_or_create_master_key(self) -> bytes:
        """
        Load master key from file or create new one
        
        Returns:
            bytes: Master key
        """
        if self._master_key:
            return self._master_key
        
        try:
            # Try to load existing key
            if os.path.exists(self.key_file):
                with open(self.key_file, 'rb') as f:
                    self._master_key = f.read()
                logger.info("Master key loaded from file")
            else:
                # Create new key
                self._master_key = secrets.token_bytes(32)
                
                # Save key to file with secure permissions
                os.umask(0o077)  # Only owner can read/write
                with open(self.key_file, 'wb') as f:
                    f.write(self._master_key)
                
                logger.info("New master key created and saved")
            
            # Initialize encryption with master key
            self.encryption = SecureEncryption(self._master_key)
            
            return self._master_key
            
        except Exception as e:
            logger.error("Failed to load or create master key", error=str(e))
            raise KeyDerivationError(f"Key management failed: {str(e)}")
    
    def rotate_master_key(self) -> bytes:
        """
        Rotate master key (create new one)
        
        Returns:
            bytes: New master key
        """
        try:
            # Backup old key
            if os.path.exists(self.key_file):
                backup_file = f"{self.key_file}.backup"
                os.rename(self.key_file, backup_file)
                logger.info("Old master key backed up")
            
            # Create new key
            self._master_key = secrets.token_bytes(32)
            
            # Save new key
            os.umask(0o077)
            with open(self.key_file, 'wb') as f:
                f.write(self._master_key)
            
            # Update encryption instance
            self.encryption = SecureEncryption(self._master_key)
            
            logger.info("Master key rotated successfully")
            
            return self._master_key
            
        except Exception as e:
            logger.error("Master key rotation failed", error=str(e))
            raise KeyDerivationError(f"Key rotation failed: {str(e)}")
    
    def get_encryption(self) -> SecureEncryption:
        """
        Get encryption instance
        
        Returns:
            SecureEncryption: Encryption utility
        """
        if not self.encryption:
            self.load_or_create_master_key()
        
        return self.encryption


# Global key manager instance
key_manager = KeyManager()

# Convenience functions
def encrypt_secret(secret: str) -> str:
    """Encrypt secret using global key manager"""
    encryption = key_manager.get_encryption()
    return encryption.encrypt_string(secret)

def decrypt_secret(encrypted_secret: str) -> str:
    """Decrypt secret using global key manager"""
    encryption = key_manager.get_encryption()
    return encryption.decrypt_string(encrypted_secret)

def hash_password(password: str) -> Tuple[str, str]:
    """Hash password and return hex hash and base64 salt"""
    encryption = key_manager.get_encryption()
    hashed, salt = encryption.hash_password(password)
    return hashed, base64.b64encode(salt).decode('utf-8')

def verify_password(password: str, hashed: str, salt_b64: str) -> bool:
    """Verify password against hash and base64 salt"""
    encryption = key_manager.get_encryption()
    salt = base64.b64decode(salt_b64.encode('utf-8'))
    return encryption.verify_password(password, hashed, salt)


# Export main classes and functions
__all__ = [
    'SecureEncryption',
    'KeyManager',
    'EncryptionError',
    'KeyDerivationError',
    'encrypt_secret',
    'decrypt_secret',
    'hash_password',
    'verify_password',
    'key_manager'
]
