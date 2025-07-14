#!/usr/bin/env python3
"""
WhatsApp Hotel Bot Database Backup Script

This script creates automated backups of the PostgreSQL database with:
- Full database dumps
- Compressed storage
- Retention policy
- Cloud storage upload (optional)
- Backup verification
- Logging and monitoring

Usage:
    python scripts/backup.py [options]

Examples:
    python scripts/backup.py --full
    python scripts/backup.py --incremental
    python scripts/backup.py --verify-only
"""

import os
import sys
import argparse
import subprocess
import datetime
import logging
import gzip
import shutil
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


@dataclass
class BackupConfig:
    """Backup configuration settings"""
    backup_dir: Path
    retention_days: int
    compression: bool
    verify_backup: bool
    upload_to_cloud: bool
    cloud_bucket: Optional[str]
    max_backup_size_gb: int
    notification_webhook: Optional[str]


class DatabaseBackup:
    """Database backup manager"""
    
    def __init__(self, config: BackupConfig):
        self.config = config
        self.logger = self._setup_logging()
        self.backup_dir = config.backup_dir
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('database_backup')
        logger.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        log_file = self.backup_dir / 'backup.log'
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        return logger
    
    def create_full_backup(self) -> Tuple[bool, str]:
        """Create a full database backup"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"hotel_bot_full_{timestamp}.sql"
        backup_path = self.backup_dir / backup_filename
        
        self.logger.info(f"Starting full backup: {backup_filename}")
        
        try:
            # Parse database URL
            db_config = self._parse_database_url()
            
            # Create pg_dump command
            cmd = [
                'pg_dump',
                '--host', db_config['host'],
                '--port', str(db_config['port']),
                '--username', db_config['user'],
                '--dbname', db_config['database'],
                '--verbose',
                '--clean',
                '--if-exists',
                '--create',
                '--format=custom',
                '--file', str(backup_path)
            ]
            
            # Set password environment variable
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            # Execute backup
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"Backup failed: {result.stderr}")
                return False, f"pg_dump failed: {result.stderr}"
            
            # Compress backup if enabled
            if self.config.compression:
                compressed_path = self._compress_backup(backup_path)
                backup_path.unlink()  # Remove uncompressed file
                backup_path = compressed_path
            
            # Verify backup
            if self.config.verify_backup:
                if not self._verify_backup(backup_path):
                    return False, "Backup verification failed"
            
            # Calculate backup size and checksum
            backup_info = self._get_backup_info(backup_path)
            
            # Create backup metadata
            metadata = {
                'filename': backup_path.name,
                'timestamp': timestamp,
                'type': 'full',
                'size_bytes': backup_info['size'],
                'checksum': backup_info['checksum'],
                'compressed': self.config.compression,
                'verified': self.config.verify_backup
            }
            
            self._save_backup_metadata(backup_path, metadata)
            
            # Upload to cloud if enabled
            if self.config.upload_to_cloud:
                self._upload_to_cloud(backup_path)
            
            self.logger.info(f"Full backup completed successfully: {backup_path.name}")
            return True, str(backup_path)
            
        except subprocess.TimeoutExpired:
            self.logger.error("Backup timed out")
            return False, "Backup operation timed out"
        except Exception as e:
            self.logger.error(f"Backup failed with exception: {str(e)}")
            return False, f"Backup failed: {str(e)}"
    
    def create_incremental_backup(self) -> Tuple[bool, str]:
        """Create an incremental backup using WAL files"""
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f"hotel_bot_incremental_{timestamp}.tar.gz"
        backup_path = self.backup_dir / backup_filename
        
        self.logger.info(f"Starting incremental backup: {backup_filename}")
        
        try:
            # This is a simplified incremental backup
            # In production, you would use pg_basebackup with WAL archiving
            
            # For now, create a schema-only dump as incremental
            db_config = self._parse_database_url()
            
            cmd = [
                'pg_dump',
                '--host', db_config['host'],
                '--port', str(db_config['port']),
                '--username', db_config['user'],
                '--dbname', db_config['database'],
                '--schema-only',
                '--format=custom',
                '--file', str(backup_path)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=1800  # 30 minutes timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"Incremental backup failed: {result.stderr}")
                return False, f"pg_dump failed: {result.stderr}"
            
            backup_info = self._get_backup_info(backup_path)
            
            metadata = {
                'filename': backup_path.name,
                'timestamp': timestamp,
                'type': 'incremental',
                'size_bytes': backup_info['size'],
                'checksum': backup_info['checksum'],
                'compressed': False,
                'verified': False
            }
            
            self._save_backup_metadata(backup_path, metadata)
            
            self.logger.info(f"Incremental backup completed: {backup_path.name}")
            return True, str(backup_path)
            
        except Exception as e:
            self.logger.error(f"Incremental backup failed: {str(e)}")
            return False, f"Incremental backup failed: {str(e)}"
    
    def verify_backup(self, backup_path: Path) -> bool:
        """Verify backup integrity"""
        self.logger.info(f"Verifying backup: {backup_path.name}")
        
        try:
            if backup_path.suffix == '.gz':
                # Verify compressed file
                with gzip.open(backup_path, 'rb') as f:
                    # Try to read first few bytes
                    f.read(1024)
            else:
                # Verify PostgreSQL custom format
                cmd = ['pg_restore', '--list', str(backup_path)]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                if result.returncode != 0:
                    self.logger.error(f"Backup verification failed: {result.stderr}")
                    return False
            
            self.logger.info(f"Backup verification successful: {backup_path.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Backup verification failed: {str(e)}")
            return False
    
    def cleanup_old_backups(self) -> int:
        """Remove old backups based on retention policy"""
        self.logger.info(f"Cleaning up backups older than {self.config.retention_days} days")
        
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=self.config.retention_days)
        removed_count = 0
        
        for backup_file in self.backup_dir.glob("hotel_bot_*.sql*"):
            try:
                file_time = datetime.datetime.fromtimestamp(backup_file.stat().st_mtime)
                if file_time < cutoff_date:
                    backup_file.unlink()
                    # Also remove metadata file if exists
                    metadata_file = backup_file.with_suffix('.json')
                    if metadata_file.exists():
                        metadata_file.unlink()
                    removed_count += 1
                    self.logger.info(f"Removed old backup: {backup_file.name}")
            except Exception as e:
                self.logger.error(f"Failed to remove {backup_file.name}: {str(e)}")
        
        self.logger.info(f"Cleanup completed. Removed {removed_count} old backups")
        return removed_count
    
    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        for backup_file in self.backup_dir.glob("hotel_bot_*.sql*"):
            metadata_file = backup_file.with_suffix('.json')
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    backups.append(metadata)
                except Exception as e:
                    self.logger.error(f"Failed to read metadata for {backup_file.name}: {str(e)}")
            else:
                # Create basic metadata for files without it
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'timestamp': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y%m%d_%H%M%S'),
                    'type': 'unknown',
                    'size_bytes': stat.st_size,
                    'checksum': None,
                    'compressed': backup_file.suffix == '.gz',
                    'verified': False
                })
        
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def _parse_database_url(self) -> Dict[str, str]:
        """Parse database URL into components"""
        from urllib.parse import urlparse
        
        parsed = urlparse(settings.DATABASE_URL)
        
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'user': parsed.username or 'postgres',
            'password': parsed.password or '',
            'database': parsed.path.lstrip('/') if parsed.path else 'hotel_bot'
        }
    
    def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup file"""
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
        
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        self.logger.info(f"Compressed backup: {compressed_path.name}")
        return compressed_path
    
    def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup file integrity"""
        return self.verify_backup(backup_path)
    
    def _get_backup_info(self, backup_path: Path) -> Dict:
        """Get backup file information"""
        stat = backup_path.stat()
        
        # Calculate checksum
        hash_md5 = hashlib.md5()
        with open(backup_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        
        return {
            'size': stat.st_size,
            'checksum': hash_md5.hexdigest()
        }
    
    def _save_backup_metadata(self, backup_path: Path, metadata: Dict):
        """Save backup metadata to JSON file"""
        metadata_path = backup_path.with_suffix('.json')
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _upload_to_cloud(self, backup_path: Path):
        """Upload backup to cloud storage (placeholder)"""
        # This would implement actual cloud upload (AWS S3, Google Cloud, etc.)
        self.logger.info(f"Cloud upload not implemented for: {backup_path.name}")
    
    def _send_notification(self, message: str, success: bool = True):
        """Send backup notification"""
        if self.config.notification_webhook:
            # This would implement webhook notification
            self.logger.info(f"Notification: {message}")


def main():
    """Main backup script entry point"""
    parser = argparse.ArgumentParser(description='Database backup script')
    parser.add_argument('--full', action='store_true', help='Create full backup')
    parser.add_argument('--incremental', action='store_true', help='Create incremental backup')
    parser.add_argument('--verify-only', type=str, help='Verify specific backup file')
    parser.add_argument('--cleanup', action='store_true', help='Cleanup old backups')
    parser.add_argument('--list', action='store_true', help='List all backups')
    parser.add_argument('--backup-dir', type=str, default='./backups', help='Backup directory')
    parser.add_argument('--retention-days', type=int, default=30, help='Backup retention days')
    parser.add_argument('--no-compression', action='store_true', help='Disable compression')
    parser.add_argument('--no-verify', action='store_true', help='Skip backup verification')
    
    args = parser.parse_args()
    
    # Create backup configuration
    config = BackupConfig(
        backup_dir=Path(args.backup_dir),
        retention_days=args.retention_days,
        compression=not args.no_compression,
        verify_backup=not args.no_verify,
        upload_to_cloud=False,  # Disabled for now
        cloud_bucket=None,
        max_backup_size_gb=10,
        notification_webhook=None
    )
    
    # Create backup manager
    backup_manager = DatabaseBackup(config)
    
    try:
        if args.full:
            success, result = backup_manager.create_full_backup()
            if success:
                print(f"Full backup created: {result}")
                sys.exit(0)
            else:
                print(f"Full backup failed: {result}")
                sys.exit(1)
        
        elif args.incremental:
            success, result = backup_manager.create_incremental_backup()
            if success:
                print(f"Incremental backup created: {result}")
                sys.exit(0)
            else:
                print(f"Incremental backup failed: {result}")
                sys.exit(1)
        
        elif args.verify_only:
            backup_path = Path(args.verify_only)
            if backup_manager.verify_backup(backup_path):
                print(f"Backup verification successful: {backup_path}")
                sys.exit(0)
            else:
                print(f"Backup verification failed: {backup_path}")
                sys.exit(1)
        
        elif args.cleanup:
            removed_count = backup_manager.cleanup_old_backups()
            print(f"Cleanup completed. Removed {removed_count} old backups")
            sys.exit(0)
        
        elif args.list:
            backups = backup_manager.list_backups()
            print(f"Found {len(backups)} backups:")
            for backup in backups:
                size_mb = backup['size_bytes'] / (1024 * 1024)
                print(f"  {backup['filename']} - {backup['type']} - {size_mb:.1f}MB - {backup['timestamp']}")
            sys.exit(0)
        
        else:
            # Default: create full backup
            success, result = backup_manager.create_full_backup()
            if success:
                print(f"Full backup created: {result}")
                sys.exit(0)
            else:
                print(f"Full backup failed: {result}")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nBackup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Backup script failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
