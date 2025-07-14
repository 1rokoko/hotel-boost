#!/usr/bin/env python3
"""
Migration script for moving secrets from environment variables to secure storage

This script migrates existing secrets from environment variables and configuration
files to the encrypted secrets management system.
"""

import os
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.secrets_manager import SecretsManager, SecretType
from app.core.vault_integration import VaultSecretsManager
from app.core.config import settings
import structlog

logger = structlog.get_logger(__name__)


# Mapping of environment variables to secret types
SECRET_MAPPING = {
    # Database credentials
    'DATABASE_URL': SecretType.DATABASE_CREDENTIAL,
    'POSTGRES_USER': SecretType.DATABASE_CREDENTIAL,
    'POSTGRES_PASSWORD': SecretType.DATABASE_CREDENTIAL,
    'POSTGRES_DB': SecretType.DATABASE_CREDENTIAL,
    
    # Redis credentials
    'REDIS_URL': SecretType.DATABASE_CREDENTIAL,
    'REDIS_PASSWORD': SecretType.PASSWORD,
    
    # API Keys
    'GREEN_API_TOKEN': SecretType.API_KEY,
    'GREEN_API_INSTANCE_ID': SecretType.API_KEY,
    'DEEPSEEK_API_KEY': SecretType.API_KEY,
    
    # JWT and encryption
    'SECRET_KEY': SecretType.JWT_SECRET,
    'JWT_SECRET_KEY': SecretType.JWT_SECRET,
    'ENCRYPTION_KEY': SecretType.ENCRYPTION_KEY,
    
    # OAuth secrets
    'OAUTH_CLIENT_SECRET': SecretType.OAUTH_SECRET,
    'GOOGLE_CLIENT_SECRET': SecretType.OAUTH_SECRET,
    'FACEBOOK_CLIENT_SECRET': SecretType.OAUTH_SECRET,
    
    # Webhook tokens
    'WEBHOOK_SECRET': SecretType.WEBHOOK_TOKEN,
    'WEBHOOK_TOKEN': SecretType.WEBHOOK_TOKEN,
    
    # Vault credentials
    'VAULT_TOKEN': SecretType.API_KEY,
    'VAULT_PASSWORD': SecretType.PASSWORD,
    'VAULT_SECRET_ID': SecretType.API_KEY,
    
    # Email credentials
    'SMTP_PASSWORD': SecretType.PASSWORD,
    'EMAIL_PASSWORD': SecretType.PASSWORD,
    
    # Cloud provider credentials
    'AWS_SECRET_ACCESS_KEY': SecretType.API_KEY,
    'AZURE_CLIENT_SECRET': SecretType.API_KEY,
    'GCP_SERVICE_ACCOUNT_KEY': SecretType.API_KEY,
    
    # Monitoring and logging
    'SENTRY_DSN': SecretType.API_KEY,
    'DATADOG_API_KEY': SecretType.API_KEY,
    'NEW_RELIC_LICENSE_KEY': SecretType.API_KEY,
}


class SecretsMigrator:
    """Handles migration of secrets to secure storage"""
    
    def __init__(
        self,
        use_vault: bool = False,
        dry_run: bool = False,
        backup_env: bool = True
    ):
        """
        Initialize secrets migrator
        
        Args:
            use_vault: Use Vault for storage instead of local encrypted storage
            dry_run: Only show what would be migrated without actually doing it
            backup_env: Create backup of environment variables
        """
        self.use_vault = use_vault
        self.dry_run = dry_run
        self.backup_env = backup_env
        
        # Initialize secrets manager
        if use_vault:
            self.secrets_manager = VaultSecretsManager.from_environment()
            if not self.secrets_manager.vault_client:
                logger.error("Vault client not available, falling back to local storage")
                self.secrets_manager = SecretsManager()
                self.use_vault = False
        else:
            self.secrets_manager = SecretsManager()
        
        logger.info(
            "Secrets migrator initialized",
            use_vault=self.use_vault,
            dry_run=self.dry_run,
            backup_env=self.backup_env
        )
    
    def backup_environment_variables(self, backup_file: str = ".env.backup") -> bool:
        """
        Create backup of current environment variables
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            bool: True if backup created successfully
        """
        if self.dry_run:
            logger.info("DRY RUN: Would create environment backup", backup_file=backup_file)
            return True
        
        try:
            with open(backup_file, 'w') as f:
                f.write("# Environment variables backup\n")
                f.write(f"# Created by secrets migration script\n\n")
                
                for env_var in SECRET_MAPPING.keys():
                    value = os.getenv(env_var)
                    if value:
                        # Mask sensitive values in backup
                        if len(value) > 8:
                            masked_value = value[:4] + "*" * (len(value) - 8) + value[-4:]
                        else:
                            masked_value = "*" * len(value)
                        
                        f.write(f"# {env_var}={masked_value}\n")
                        f.write(f"{env_var}={value}\n\n")
            
            logger.info("Environment variables backed up", backup_file=backup_file)
            return True
            
        except Exception as e:
            logger.error("Failed to backup environment variables", error=str(e))
            return False
    
    def migrate_environment_secrets(self) -> Dict[str, bool]:
        """
        Migrate secrets from environment variables
        
        Returns:
            Dict[str, bool]: Migration results for each secret
        """
        results = {}
        migrated_count = 0
        
        logger.info("Starting environment secrets migration")
        
        for env_var, secret_type in SECRET_MAPPING.items():
            env_value = os.getenv(env_var)
            
            if not env_value:
                logger.debug("Environment variable not set", env_var=env_var)
                results[env_var] = False
                continue
            
            secret_id = env_var.lower()
            
            if self.dry_run:
                logger.info(
                    "DRY RUN: Would migrate secret",
                    env_var=env_var,
                    secret_id=secret_id,
                    secret_type=secret_type.value,
                    value_length=len(env_value)
                )
                results[env_var] = True
                migrated_count += 1
                continue
            
            try:
                if self.use_vault:
                    # Store in Vault
                    success = self.secrets_manager.set_secret(
                        path=f"app/{secret_id}",
                        secret_data=env_value
                    )
                else:
                    # Store in local encrypted storage
                    success = self.secrets_manager.set_secret(
                        secret_id=secret_id,
                        secret_value=env_value,
                        secret_type=secret_type,
                        description=f"Migrated from environment variable {env_var}"
                    )
                
                if success:
                    migrated_count += 1
                    logger.info(
                        "Secret migrated successfully",
                        env_var=env_var,
                        secret_id=secret_id,
                        secret_type=secret_type.value
                    )
                else:
                    logger.error(
                        "Failed to migrate secret",
                        env_var=env_var,
                        secret_id=secret_id
                    )
                
                results[env_var] = success
                
            except Exception as e:
                logger.error(
                    "Error migrating secret",
                    env_var=env_var,
                    secret_id=secret_id,
                    error=str(e)
                )
                results[env_var] = False
        
        logger.info(
            "Environment secrets migration completed",
            migrated_count=migrated_count,
            total_secrets=len(SECRET_MAPPING),
            success_rate=f"{migrated_count/len(SECRET_MAPPING)*100:.1f}%"
        )
        
        return results
    
    def migrate_hotel_secrets(self) -> Dict[str, bool]:
        """
        Migrate hotel-specific secrets from database
        
        Returns:
            Dict[str, bool]: Migration results for each hotel
        """
        results = {}
        
        if self.dry_run:
            logger.info("DRY RUN: Would migrate hotel secrets from database")
            return results
        
        try:
            # Import here to avoid circular imports
            from app.database import AsyncSessionLocal
            from app.models.hotel import Hotel
            from sqlalchemy import select
            
            async def migrate_hotels():
                async with AsyncSessionLocal() as session:
                    # Get all hotels
                    result = await session.execute(select(Hotel))
                    hotels = result.scalars().all()
                    
                    for hotel in hotels:
                        hotel_results = {}
                        
                        # Migrate Green API credentials
                        if hotel.green_api_instance_id:
                            secret_id = f"hotel_{hotel.id}_green_api_instance_id"
                            success = self.secrets_manager.set_secret(
                                secret_id=secret_id,
                                secret_value=hotel.green_api_instance_id,
                                secret_type=SecretType.API_KEY,
                                description=f"Green API instance ID for hotel {hotel.name}"
                            )
                            hotel_results['green_api_instance_id'] = success
                        
                        if hotel.green_api_token:
                            secret_id = f"hotel_{hotel.id}_green_api_token"
                            success = self.secrets_manager.set_secret(
                                secret_id=secret_id,
                                secret_value=hotel.green_api_token,
                                secret_type=SecretType.API_KEY,
                                description=f"Green API token for hotel {hotel.name}"
                            )
                            hotel_results['green_api_token'] = success
                        
                        if hotel.green_api_webhook_token:
                            secret_id = f"hotel_{hotel.id}_webhook_token"
                            success = self.secrets_manager.set_secret(
                                secret_id=secret_id,
                                secret_value=hotel.green_api_webhook_token,
                                secret_type=SecretType.WEBHOOK_TOKEN,
                                description=f"Webhook token for hotel {hotel.name}"
                            )
                            hotel_results['webhook_token'] = success
                        
                        results[f"hotel_{hotel.id}"] = hotel_results
                        
                        logger.info(
                            "Hotel secrets migrated",
                            hotel_id=hotel.id,
                            hotel_name=hotel.name,
                            secrets_migrated=len([k for k, v in hotel_results.items() if v])
                        )
            
            # Run async migration
            import asyncio
            asyncio.run(migrate_hotels())
            
        except Exception as e:
            logger.error("Failed to migrate hotel secrets", error=str(e))
        
        return results
    
    def verify_migration(self) -> bool:
        """
        Verify that migrated secrets can be retrieved
        
        Returns:
            bool: True if verification successful
        """
        logger.info("Verifying migrated secrets")
        
        verification_failed = []
        
        for env_var in SECRET_MAPPING.keys():
            env_value = os.getenv(env_var)
            if not env_value:
                continue
            
            secret_id = env_var.lower()
            
            try:
                if self.use_vault:
                    retrieved_value = self.secrets_manager.get_secret(f"app/{secret_id}")
                else:
                    retrieved_value = self.secrets_manager.get_secret(secret_id)
                
                if retrieved_value != env_value:
                    verification_failed.append(env_var)
                    logger.error(
                        "Secret verification failed",
                        env_var=env_var,
                        secret_id=secret_id,
                        values_match=retrieved_value == env_value
                    )
                else:
                    logger.debug("Secret verification passed", env_var=env_var)
                    
            except Exception as e:
                verification_failed.append(env_var)
                logger.error(
                    "Secret verification error",
                    env_var=env_var,
                    error=str(e)
                )
        
        if verification_failed:
            logger.error(
                "Secret verification failed for some secrets",
                failed_secrets=verification_failed,
                failed_count=len(verification_failed)
            )
            return False
        
        logger.info("All migrated secrets verified successfully")
        return True
    
    def generate_migration_report(self, results: Dict[str, bool]) -> str:
        """
        Generate migration report
        
        Args:
            results: Migration results
            
        Returns:
            str: Migration report
        """
        successful = [k for k, v in results.items() if v]
        failed = [k for k, v in results.items() if not v]
        
        report = f"""
Secrets Migration Report
========================

Migration Type: {'Vault' if self.use_vault else 'Local Encrypted Storage'}
Dry Run: {self.dry_run}

Summary:
- Total secrets processed: {len(results)}
- Successfully migrated: {len(successful)}
- Failed migrations: {len(failed)}
- Success rate: {len(successful)/len(results)*100:.1f}%

Successful migrations:
{chr(10).join(f"  ✓ {secret}" for secret in successful)}

Failed migrations:
{chr(10).join(f"  ✗ {secret}" for secret in failed)}

Next Steps:
1. Verify migrated secrets are accessible
2. Update application configuration to use secrets manager
3. Remove environment variables from production systems
4. Update deployment scripts and documentation
"""
        
        return report


def main():
    """Main migration script"""
    parser = argparse.ArgumentParser(description="Migrate secrets to secure storage")
    parser.add_argument(
        "--vault",
        action="store_true",
        help="Use HashiCorp Vault for storage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without actually doing it"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip creating backup of environment variables"
    )
    parser.add_argument(
        "--include-hotels",
        action="store_true",
        help="Also migrate hotel-specific secrets from database"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify migrated secrets after migration"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Initialize migrator
    migrator = SecretsMigrator(
        use_vault=args.vault,
        dry_run=args.dry_run,
        backup_env=not args.no_backup
    )
    
    try:
        # Create backup if requested
        if not args.no_backup and not args.dry_run:
            migrator.backup_environment_variables()
        
        # Migrate environment secrets
        env_results = migrator.migrate_environment_secrets()
        
        # Migrate hotel secrets if requested
        hotel_results = {}
        if args.include_hotels:
            hotel_results = migrator.migrate_hotel_secrets()
        
        # Verify migration if requested
        if args.verify and not args.dry_run:
            verification_success = migrator.verify_migration()
            if not verification_success:
                logger.error("Migration verification failed")
                sys.exit(1)
        
        # Generate and print report
        all_results = {**env_results, **hotel_results}
        report = migrator.generate_migration_report(all_results)
        print(report)
        
        # Exit with appropriate code
        failed_count = len([k for k, v in all_results.items() if not v])
        if failed_count > 0:
            logger.error(f"Migration completed with {failed_count} failures")
            sys.exit(1)
        else:
            logger.info("Migration completed successfully")
            sys.exit(0)
            
    except Exception as e:
        logger.error("Migration failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
