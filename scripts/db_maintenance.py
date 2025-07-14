#!/usr/bin/env python3
"""
WhatsApp Hotel Bot Database Maintenance Script

This script performs routine database maintenance tasks:
- VACUUM and ANALYZE operations
- Index maintenance and rebuilding
- Statistics updates
- Dead tuple cleanup
- Performance monitoring
- Health checks

Usage:
    python scripts/db_maintenance.py [options]

Examples:
    python scripts/db_maintenance.py --vacuum-all
    python scripts/db_maintenance.py --analyze-all
    python scripts/db_maintenance.py --reindex --table hotels
    python scripts/db_maintenance.py --health-check
"""

import os
import sys
import argparse
import asyncio
import logging
import datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.core.database import get_async_session
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class MaintenanceConfig:
    """Maintenance configuration settings"""
    vacuum_full: bool
    analyze_tables: bool
    reindex_tables: bool
    update_statistics: bool
    check_health: bool
    target_tables: Optional[List[str]]
    dry_run: bool
    verbose: bool


class DatabaseMaintenance:
    """Database maintenance manager"""
    
    def __init__(self, config: MaintenanceConfig):
        self.config = config
        self.logger = self._setup_logging()
        
    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logger = logging.getLogger('database_maintenance')
        level = logging.DEBUG if self.config.verbose else logging.INFO
        logger.setLevel(level)
        
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    async def run_maintenance(self) -> Dict[str, bool]:
        """Run all requested maintenance operations"""
        results = {}
        
        async with get_async_session() as session:
            if self.config.check_health:
                results['health_check'] = await self._health_check(session)
            
            if self.config.vacuum_full:
                results['vacuum'] = await self._vacuum_tables(session)
            
            if self.config.analyze_tables:
                results['analyze'] = await self._analyze_tables(session)
            
            if self.config.reindex_tables:
                results['reindex'] = await self._reindex_tables(session)
            
            if self.config.update_statistics:
                results['statistics'] = await self._update_statistics(session)
        
        return results
    
    async def _health_check(self, session: AsyncSession) -> bool:
        """Perform comprehensive database health check"""
        self.logger.info("Performing database health check...")
        
        try:
            # Check database connectivity
            result = await session.execute(text("SELECT 1"))
            if not result.scalar():
                self.logger.error("Database connectivity check failed")
                return False
            
            # Check database size
            size_query = """
                SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                       pg_database_size(current_database()) as size_bytes
            """
            result = await session.execute(text(size_query))
            size_info = result.fetchone()
            self.logger.info(f"Database size: {size_info.size}")
            
            # Check table sizes
            table_size_query = """
                SELECT schemaname, tablename,
                       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
                       pg_total_relation_size(schemaname||'.'||tablename) as size_bytes
                FROM pg_tables 
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
                LIMIT 10
            """
            result = await session.execute(text(table_size_query))
            tables = result.fetchall()
            
            self.logger.info("Largest tables:")
            for table in tables:
                self.logger.info(f"  {table.tablename}: {table.size}")
            
            # Check for bloated tables
            bloat_query = """
                SELECT schemaname, tablename,
                       ROUND(CASE WHEN otta=0 THEN 0.0 ELSE sml.relpages/otta::numeric END,1) AS tbloat,
                       CASE WHEN relpages < otta THEN 0 ELSE relpages::bigint - otta END AS wastedpages,
                       CASE WHEN relpages < otta THEN 0 ELSE bs*(sml.relpages-otta)::bigint END AS wastedbytes,
                       CASE WHEN relpages < otta THEN '0 bytes'::text ELSE pg_size_pretty((bs*(relpages-otta))::bigint) END AS wastedsize
                FROM (
                    SELECT schemaname, tablename, cc.reltuples, cc.relpages, bs,
                           CEIL((cc.reltuples*((datahdr+ma-
                               (CASE WHEN datahdr%ma=0 THEN ma ELSE datahdr%ma END))+nullhdr2+4))/(bs-20::float)) AS otta
                    FROM (
                        SELECT ma,bs,schemaname,tablename,
                               (datawidth+(hdr+ma-(case when hdr%ma=0 THEN ma ELSE hdr%ma END)))::numeric AS datahdr,
                               (maxfracsum*(nullhdr+ma-(case when nullhdr%ma=0 THEN ma ELSE nullhdr%ma END))) AS nullhdr2
                        FROM (
                            SELECT schemaname, tablename, hdr, ma, bs,
                                   SUM((1-null_frac)*avg_width) AS datawidth,
                                   MAX(null_frac) AS maxfracsum,
                                   hdr+(
                                       SELECT 1+count(*)/8
                                       FROM pg_stats s2
                                       WHERE null_frac<>0 AND s2.schemaname = s.schemaname AND s2.tablename = s.tablename
                                   ) AS nullhdr
                            FROM pg_stats s, (
                                SELECT (SELECT current_setting('block_size')::numeric) AS bs,
                                       CASE WHEN substring(SPLIT_PART(v, ' ', 2) FROM '#"[0-9]+.[0-9]+#"%' for '#')
                                            IN ('8.0','8.1','8.2') THEN 27 ELSE 23 END AS hdr,
                                       CASE WHEN v ~ 'mingw32' OR v ~ '64-bit' THEN 8 ELSE 4 END AS ma
                                FROM (SELECT version() AS v) AS foo
                            ) AS constants
                            WHERE schemaname = 'public'
                            GROUP BY schemaname, tablename, hdr, ma, bs
                        ) AS foo
                    ) AS rs
                    JOIN pg_class cc ON cc.relname = rs.tablename
                    JOIN pg_namespace nn ON cc.relnamespace = nn.oid AND nn.nspname = rs.schemaname AND nn.nspname <> 'information_schema'
                ) AS sml
                WHERE sml.relpages - otta > 0 OR cc.relpages < otta
                ORDER BY wastedbytes DESC
                LIMIT 10
            """
            
            try:
                result = await session.execute(text(bloat_query))
                bloated_tables = result.fetchall()
                
                if bloated_tables:
                    self.logger.info("Tables with potential bloat:")
                    for table in bloated_tables:
                        if table.tbloat > 1.5:  # More than 50% bloat
                            self.logger.warning(f"  {table.tablename}: {table.tbloat}x bloat, {table.wastedsize} wasted")
            except Exception as e:
                self.logger.warning(f"Could not check table bloat: {str(e)}")
            
            # Check index usage
            index_usage_query = """
                SELECT schemaname, tablename, indexname, idx_tup_read, idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE idx_tup_read = 0 AND idx_tup_fetch = 0
                ORDER BY schemaname, tablename, indexname
            """
            result = await session.execute(text(index_usage_query))
            unused_indexes = result.fetchall()
            
            if unused_indexes:
                self.logger.warning("Potentially unused indexes:")
                for idx in unused_indexes:
                    self.logger.warning(f"  {idx.indexname} on {idx.tablename}")
            
            # Check connection count
            connection_query = """
                SELECT count(*) as active_connections,
                       (SELECT setting::int FROM pg_settings WHERE name = 'max_connections') as max_connections
                FROM pg_stat_activity
                WHERE state = 'active'
            """
            result = await session.execute(text(connection_query))
            conn_info = result.fetchone()
            conn_usage = (conn_info.active_connections / conn_info.max_connections) * 100
            
            self.logger.info(f"Active connections: {conn_info.active_connections}/{conn_info.max_connections} ({conn_usage:.1f}%)")
            
            if conn_usage > 80:
                self.logger.warning("High connection usage detected")
            
            self.logger.info("Database health check completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Health check failed: {str(e)}")
            return False
    
    async def _vacuum_tables(self, session: AsyncSession) -> bool:
        """Perform VACUUM operation on tables"""
        self.logger.info("Starting VACUUM operation...")
        
        try:
            tables = self.config.target_tables or await self._get_all_tables(session)
            
            for table in tables:
                self.logger.info(f"Vacuuming table: {table}")
                
                if self.config.dry_run:
                    self.logger.info(f"DRY RUN: Would vacuum {table}")
                    continue
                
                # Use VACUUM ANALYZE for better performance
                vacuum_query = f"VACUUM ANALYZE {table}"
                await session.execute(text(vacuum_query))
                await session.commit()
                
                self.logger.info(f"Completed vacuum for: {table}")
            
            self.logger.info("VACUUM operation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"VACUUM operation failed: {str(e)}")
            return False
    
    async def _analyze_tables(self, session: AsyncSession) -> bool:
        """Perform ANALYZE operation on tables"""
        self.logger.info("Starting ANALYZE operation...")
        
        try:
            tables = self.config.target_tables or await self._get_all_tables(session)
            
            for table in tables:
                self.logger.info(f"Analyzing table: {table}")
                
                if self.config.dry_run:
                    self.logger.info(f"DRY RUN: Would analyze {table}")
                    continue
                
                analyze_query = f"ANALYZE {table}"
                await session.execute(text(analyze_query))
                await session.commit()
                
                self.logger.info(f"Completed analysis for: {table}")
            
            self.logger.info("ANALYZE operation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"ANALYZE operation failed: {str(e)}")
            return False
    
    async def _reindex_tables(self, session: AsyncSession) -> bool:
        """Perform REINDEX operation on tables"""
        self.logger.info("Starting REINDEX operation...")
        
        try:
            tables = self.config.target_tables or await self._get_all_tables(session)
            
            for table in tables:
                self.logger.info(f"Reindexing table: {table}")
                
                if self.config.dry_run:
                    self.logger.info(f"DRY RUN: Would reindex {table}")
                    continue
                
                reindex_query = f"REINDEX TABLE {table}"
                await session.execute(text(reindex_query))
                await session.commit()
                
                self.logger.info(f"Completed reindex for: {table}")
            
            self.logger.info("REINDEX operation completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"REINDEX operation failed: {str(e)}")
            return False
    
    async def _update_statistics(self, session: AsyncSession) -> bool:
        """Update database statistics"""
        self.logger.info("Updating database statistics...")
        
        try:
            if self.config.dry_run:
                self.logger.info("DRY RUN: Would update statistics")
                return True
            
            # Reset statistics
            await session.execute(text("SELECT pg_stat_reset()"))
            await session.commit()
            
            self.logger.info("Database statistics updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Statistics update failed: {str(e)}")
            return False
    
    async def _get_all_tables(self, session: AsyncSession) -> List[str]:
        """Get list of all user tables"""
        query = """
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        """
        result = await session.execute(text(query))
        return [row.tablename for row in result.fetchall()]


def main():
    """Main maintenance script entry point"""
    parser = argparse.ArgumentParser(description='Database maintenance script')
    parser.add_argument('--vacuum-all', action='store_true', help='Vacuum all tables')
    parser.add_argument('--analyze-all', action='store_true', help='Analyze all tables')
    parser.add_argument('--reindex', action='store_true', help='Reindex tables')
    parser.add_argument('--update-stats', action='store_true', help='Update database statistics')
    parser.add_argument('--health-check', action='store_true', help='Perform health check')
    parser.add_argument('--table', action='append', help='Target specific table (can be used multiple times)')
    parser.add_argument('--dry-run', action='store_true', help='Perform dry run without actual operations')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    parser.add_argument('--all', action='store_true', help='Perform all maintenance operations')
    
    args = parser.parse_args()
    
    # If --all is specified, enable all operations
    if args.all:
        args.vacuum_all = True
        args.analyze_all = True
        args.reindex = True
        args.update_stats = True
        args.health_check = True
    
    # If no specific operations are requested, show help
    if not any([args.vacuum_all, args.analyze_all, args.reindex, 
                args.update_stats, args.health_check]):
        parser.print_help()
        sys.exit(1)
    
    # Create maintenance configuration
    config = MaintenanceConfig(
        vacuum_full=args.vacuum_all,
        analyze_tables=args.analyze_all,
        reindex_tables=args.reindex,
        update_statistics=args.update_stats,
        check_health=args.health_check,
        target_tables=args.table,
        dry_run=args.dry_run,
        verbose=args.verbose
    )
    
    # Create maintenance manager
    maintenance_manager = DatabaseMaintenance(config)
    
    try:
        # Run maintenance operations
        results = asyncio.run(maintenance_manager.run_maintenance())
        
        # Print summary
        print("\n" + "="*60)
        print("MAINTENANCE SUMMARY")
        print("="*60)
        
        all_successful = True
        for operation, success in results.items():
            status = "SUCCESS" if success else "FAILED"
            print(f"{operation.upper()}: {status}")
            if not success:
                all_successful = False
        
        print("="*60)
        
        if all_successful:
            print("All maintenance operations completed successfully!")
            sys.exit(0)
        else:
            print("Some maintenance operations failed. Check logs for details.")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nMaintenance interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Maintenance script failed: {str(e)}")
        sys.exit(1)


if __name__ == '__main__':
    main()
