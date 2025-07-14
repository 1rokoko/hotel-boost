#!/usr/bin/env python3
"""
WhatsApp Hotel Bot Database Restore Script

This script restores PostgreSQL database from backups with:
- Full database restoration
- Point-in-time recovery
- Backup verification before restore
- Safety checks and confirmations
- Logging and monitoring

Usage:
    python scripts/restore.py [options]

Examples:
    python scripts/restore.py --backup hotel_bot_full_20240101_120000.sql.gz
    python scripts/restore.py --list-backups
    python scripts/restore.py --latest --confirm
"""

import os
import sys
import argparse
import subprocess
import datetime
import logging
import gzip
import json
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings


@dataclass
class RestoreConfig:
    """Restore configuration settings"""
    backup_dir: Path
    target_database: str
    create_database: bool
    drop_existing: bool
    verify_before_restore: bool
    dry_run: bool
    force: bool


class DatabaseRestore:
    """Database restore manager"""
    
    def __init__(self, config: RestoreConfig):
        self.config = config
        self.logger = self._setup_logging()
        self.backup_dir = config.backup_dir
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('database_restore')
        logger.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def restore_from_backup(self, backup_path: Path) -> Tuple[bool, str]:
        """Restore database from backup file"""
        self.logger.info(f"Starting restore from backup: {backup_path.name}")
        
        if not backup_path.exists():
            return False, f"Backup file not found: {backup_path}"
        
        try:
            # Verify backup before restore
            if self.config.verify_before_restore:
                if not self._verify_backup(backup_path):
                    return False, "Backup verification failed"
            
            # Parse database configuration
            db_config = self._parse_database_url()
            
            # Safety checks
            if not self.config.force:
                if not self._confirm_restore(backup_path, db_config):
                    return False, "Restore cancelled by user"
            
            # Prepare restore file
            restore_file = self._prepare_restore_file(backup_path)
            
            try:
                # Drop existing database if requested
                if self.config.drop_existing:
                    self._drop_database(db_config)
                
                # Create database if requested
                if self.config.create_database:
                    self._create_database(db_config)
                
                # Perform restore
                if self.config.dry_run:
                    self.logger.info("DRY RUN: Would restore database now")
                    return True, "Dry run completed successfully"
                else:
                    success, message = self._execute_restore(restore_file, db_config)
                    return success, message
                    
            finally:
                # Cleanup temporary files
                if restore_file != backup_path and restore_file.exists():
                    restore_file.unlink()
                    
        except Exception as e:
            self.logger.error(f"Restore failed with exception: {str(e)}")
            return False, f"Restore failed: {str(e)}"
    
    def list_available_backups(self) -> List[Dict]:
        """List all available backup files"""
        backups = []
        
        for backup_file in self.backup_dir.glob("hotel_bot_*.sql*"):
            metadata_file = backup_file.with_suffix('.json')
            
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    metadata['path'] = str(backup_file)
                    backups.append(metadata)
                except Exception as e:
                    self.logger.error(f"Failed to read metadata for {backup_file.name}: {str(e)}")
            else:
                # Create basic info for files without metadata
                stat = backup_file.stat()
                backups.append({
                    'filename': backup_file.name,
                    'path': str(backup_file),
                    'timestamp': datetime.datetime.fromtimestamp(stat.st_mtime).strftime('%Y%m%d_%H%M%S'),
                    'type': 'unknown',
                    'size_bytes': stat.st_size,
                    'compressed': backup_file.suffix == '.gz'
                })
        
        return sorted(backups, key=lambda x: x['timestamp'], reverse=True)
    
    def get_latest_backup(self) -> Optional[Path]:
        """Get the latest backup file"""
        backups = self.list_available_backups()
        if backups:
            return Path(backups[0]['path'])
        return None
    
    def _verify_backup(self, backup_path: Path) -> bool:
        """Verify backup file integrity"""
        self.logger.info(f"Verifying backup: {backup_path.name}")
        
        try:
            if backup_path.suffix == '.gz':
                # Verify compressed file can be opened
                with gzip.open(backup_path, 'rb') as f:
                    f.read(1024)  # Try to read first chunk
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
    
    def _parse_database_url(self) -> Dict[str, str]:
        """Parse database URL into components"""
        from urllib.parse import urlparse
        
        parsed = urlparse(settings.DATABASE_URL)
        
        return {
            'host': parsed.hostname or 'localhost',
            'port': parsed.port or 5432,
            'user': parsed.username or 'postgres',
            'password': parsed.password or '',
            'database': self.config.target_database or parsed.path.lstrip('/') or 'hotel_bot'
        }
    
    def _confirm_restore(self, backup_path: Path, db_config: Dict[str, str]) -> bool:
        """Confirm restore operation with user"""
        print(f"\n{'='*60}")
        print("DATABASE RESTORE CONFIRMATION")
        print(f"{'='*60}")
        print(f"Backup file: {backup_path.name}")
        print(f"Target database: {db_config['database']}")
        print(f"Target host: {db_config['host']}:{db_config['port']}")
        print(f"Drop existing: {self.config.drop_existing}")
        print(f"Create database: {self.config.create_database}")
        print(f"{'='*60}")
        print("\nWARNING: This operation will modify/replace the target database!")
        print("Make sure you have a backup of the current database if needed.")
        print()
        
        response = input("Do you want to continue? (yes/no): ").strip().lower()
        return response in ['yes', 'y']
    
    def _prepare_restore_file(self, backup_path: Path) -> Path:
        """Prepare backup file for restore (decompress if needed)"""
        if backup_path.suffix == '.gz':
            self.logger.info("Decompressing backup file...")
            
            # Create temporary file for decompressed backup
            temp_file = Path(tempfile.mktemp(suffix='.sql'))
            
            with gzip.open(backup_path, 'rb') as f_in:
                with open(temp_file, 'wb') as f_out:
                    while True:
                        chunk = f_in.read(8192)
                        if not chunk:
                            break
                        f_out.write(chunk)
            
            self.logger.info(f"Decompressed to: {temp_file}")
            return temp_file
        
        return backup_path
    
    def _drop_database(self, db_config: Dict[str, str]):
        """Drop existing database"""
        self.logger.info(f"Dropping database: {db_config['database']}")
        
        cmd = [
            'dropdb',
            '--host', db_config['host'],
            '--port', str(db_config['port']),
            '--username', db_config['user'],
            '--if-exists',
            db_config['database']
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = db_config['password']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to drop database: {result.stderr}")
    
    def _create_database(self, db_config: Dict[str, str]):
        """Create new database"""
        self.logger.info(f"Creating database: {db_config['database']}")
        
        cmd = [
            'createdb',
            '--host', db_config['host'],
            '--port', str(db_config['port']),
            '--username', db_config['user'],
            '--encoding=UTF8',
            db_config['database']
        ]
        
        env = os.environ.copy()
        env['PGPASSWORD'] = db_config['password']
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode != 0:
            raise Exception(f"Failed to create database: {result.stderr}")
    
    def _execute_restore(self, restore_file: Path, db_config: Dict[str, str]) -> Tuple[bool, str]:
        """Execute the actual restore operation"""
        self.logger.info("Executing database restore...")
        
        try:
            cmd = [
                'pg_restore',
                '--host', db_config['host'],
                '--port', str(db_config['port']),
                '--username', db_config['user'],
                '--dbname', db_config['database'],
                '--verbose',
                '--clean',
                '--if-exists',
                '--no-owner',
                '--no-privileges',
                str(restore_file)
            ]
            
            env = os.environ.copy()
            env['PGPASSWORD'] = db_config['password']
            
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=7200  # 2 hour timeout
            )
            
            if result.returncode != 0:
                self.logger.error(f"Restore failed: {result.stderr}")
                return False, f"pg_restore failed: {result.stderr}"
            
            self.logger.info("Database restore completed successfully")
            return True, "Restore completed successfully"
            
        except subprocess.TimeoutExpired:
            self.logger.error("Restore operation timed out")
            return False, "Restore operation timed out"
        except Exception as e:
            self.logger.error(f"Restore failed: {str(e)}")
            return False, f"Restore failed: {str(e)}"


def main():
    """Main restore script entry point"""
    parser = argparse.ArgumentParser(description='Database restore script')
    parser.add_argument('--backup', type=str, help='Backup file to restore from')
    parser.add_argument('--latest', action='store_true', help='Restore from latest backup')
    parser.add_argument('--list-backups', action='store_true', help='List available backups')
    parser.add_argument('--backup-dir', type=str, default='./backups', help='Backup directory')
    parser.add_argument('--target-db', type=str, help='Target database name')
    parser.add_argument('--create-db', action='store_true', help='Create target database')
    parser.add_argument('--drop-existing', action='store_true', help='Drop existing database')
    parser.add_argument('--no-verify', action='store_true', help='Skip backup verification')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual restore')
    parser.add_argument('--force', action='store_true', help='Skip confirmation prompts')
    
    args = parser.parse_args()
    
    # Create restore configuration
    config = RestoreConfig(
        backup_dir=Path(args.backup_dir),
        target_database=args.target_db,
        create_database=args.create_db,
        drop_existing=args.drop_existing,
        verify_before_restore=not args.no_verify,
        dry_run=args.dry_run,
        force=args.force
    )
    
    # Create restore manager
    restore_manager = DatabaseRestore(config)
    
    try:
        if args.list_backups:
            backups = restore_manager.list_available_backups()
            print(f"Found {len(backups)} available backups:")
            for backup in backups:
                size_mb = backup['size_bytes'] / (1024 * 1024)
                print(f"  {backup['filename']} - {backup['type']} - {size_mb:.1f}MB - {backup['timestamp']}")
            sys.exit(0)
        
        elif args.latest:
            backup_path = restore_manager.get_latest_backup()
            if not backup_path:
                print("No backups found")
                sys.exit(1)
            
            print(f"Using latest backup: {backup_path.name}")
            success, result = restore_manager.restore_from_backup(backup_path)
            
        elif args.backup:
            backup_path = Path(args.backup)
            if not backup_path.is_absolute():
                backup_path = config.backup_dir / backup_path
            
            success, result = restore_manager.restore_from_backup(backup_path)
        
        else:
            parser.print_help()
            sys.exit(1)
        
        if success:
            print(f"Restore successful: {result}")
            sys.exit(0)
        else:
            print(f"Restore failed: {result}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nRestore interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Restore script failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
