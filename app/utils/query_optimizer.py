"""
Database query optimization utilities for WhatsApp Hotel Bot
Provides query analysis, N+1 detection, and performance optimization
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from sqlalchemy import text, inspect, MetaData, Table
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Query, selectinload, joinedload, contains_eager
from sqlalchemy.sql import Select
from sqlalchemy.engine import Result
import structlog

from app.core.logging import get_logger
from app.core.metrics import track_database_query
from app.utils.connection_manager import get_connection_manager

logger = get_logger(__name__)


@dataclass
class QueryMetrics:
    """Query performance metrics"""
    query_hash: str
    sql_text: str
    execution_time_ms: float
    row_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)
    table_names: List[str] = field(default_factory=list)
    join_count: int = 0
    where_conditions: int = 0
    is_slow: bool = False
    error: Optional[str] = None


@dataclass
class N1QueryDetection:
    """N+1 query detection result"""
    parent_query: str
    child_queries: List[str]
    execution_count: int
    total_time_ms: float
    suggested_fix: str


class QueryAnalyzer:
    """Analyzes database queries for performance optimization"""
    
    def __init__(self, slow_query_threshold_ms: float = 1000.0):
        self.slow_query_threshold_ms = slow_query_threshold_ms
        self.logger = logger.bind(component="query_analyzer")
        
        # Query tracking
        self.query_history: deque = deque(maxlen=10000)
        self.query_patterns: Dict[str, List[QueryMetrics]] = defaultdict(list)
        self.n1_detections: List[N1QueryDetection] = []
        
        # Performance tracking
        self.slow_queries: deque = deque(maxlen=1000)
        self.query_frequency: Dict[str, int] = defaultdict(int)
        self.table_access_patterns: Dict[str, int] = defaultdict(int)
    
    def analyze_query(self, sql_text: str) -> Dict[str, Any]:
        """Analyze a SQL query for optimization opportunities"""
        analysis = {
            "sql_text": sql_text,
            "table_names": self._extract_table_names(sql_text),
            "join_count": self._count_joins(sql_text),
            "where_conditions": self._count_where_conditions(sql_text),
            "has_order_by": "ORDER BY" in sql_text.upper(),
            "has_limit": "LIMIT" in sql_text.upper(),
            "has_subquery": "SELECT" in sql_text.upper().replace(sql_text.split()[0].upper(), "", 1),
            "optimization_suggestions": []
        }
        
        # Generate optimization suggestions
        suggestions = self._generate_optimization_suggestions(analysis)
        analysis["optimization_suggestions"] = suggestions
        
        return analysis
    
    def _extract_table_names(self, sql_text: str) -> List[str]:
        """Extract table names from SQL query"""
        # Simple regex-based extraction (could be enhanced with SQL parser)
        import re
        
        # Look for FROM and JOIN clauses
        from_pattern = r'FROM\s+(\w+)'
        join_pattern = r'JOIN\s+(\w+)'
        
        tables = set()
        
        # Extract FROM tables
        from_matches = re.findall(from_pattern, sql_text, re.IGNORECASE)
        tables.update(from_matches)
        
        # Extract JOIN tables
        join_matches = re.findall(join_pattern, sql_text, re.IGNORECASE)
        tables.update(join_matches)
        
        return list(tables)
    
    def _count_joins(self, sql_text: str) -> int:
        """Count the number of JOINs in the query"""
        return sql_text.upper().count("JOIN")
    
    def _count_where_conditions(self, sql_text: str) -> int:
        """Count WHERE conditions in the query"""
        where_clause = sql_text.upper().split("WHERE")
        if len(where_clause) < 2:
            return 0
        
        # Count AND/OR operators as indicators of multiple conditions
        conditions = where_clause[1].count("AND") + where_clause[1].count("OR") + 1
        return conditions
    
    def _generate_optimization_suggestions(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate optimization suggestions based on query analysis"""
        suggestions = []
        
        # Check for missing LIMIT on potentially large result sets
        if not analysis["has_limit"] and analysis["join_count"] > 0:
            suggestions.append("Consider adding LIMIT clause for large result sets")
        
        # Check for complex queries without ORDER BY
        if analysis["join_count"] > 2 and not analysis["has_order_by"]:
            suggestions.append("Consider adding ORDER BY for consistent results")
        
        # Check for too many joins
        if analysis["join_count"] > 5:
            suggestions.append("Consider breaking down complex joins into multiple queries")
        
        # Check for subqueries
        if analysis["has_subquery"]:
            suggestions.append("Consider using JOINs instead of subqueries for better performance")
        
        # Table-specific suggestions
        for table in analysis["table_names"]:
            if table in ["messages", "conversations", "guests"]:
                suggestions.append(f"Ensure {table} queries are filtered by hotel_id for tenant isolation")
        
        return suggestions
    
    async def track_query_execution(
        self,
        sql_text: str,
        execution_time_ms: float,
        row_count: int = 0,
        error: Optional[str] = None
    ) -> QueryMetrics:
        """Track query execution for performance analysis"""
        
        # Create query hash for pattern matching
        query_hash = self._create_query_hash(sql_text)
        
        # Analyze the query
        analysis = self.analyze_query(sql_text)
        
        # Create metrics
        metrics = QueryMetrics(
            query_hash=query_hash,
            sql_text=sql_text,
            execution_time_ms=execution_time_ms,
            row_count=row_count,
            table_names=analysis["table_names"],
            join_count=analysis["join_count"],
            where_conditions=analysis["where_conditions"],
            is_slow=execution_time_ms > self.slow_query_threshold_ms,
            error=error
        )
        
        # Store metrics
        self.query_history.append(metrics)
        self.query_patterns[query_hash].append(metrics)
        self.query_frequency[query_hash] += 1
        
        # Track table access patterns
        for table in analysis["table_names"]:
            self.table_access_patterns[table] += 1
        
        # Track slow queries
        if metrics.is_slow:
            self.slow_queries.append(metrics)
            self.logger.warning("Slow query detected",
                              execution_time_ms=execution_time_ms,
                              sql_text=sql_text[:200],
                              suggestions=analysis["optimization_suggestions"])
        
        # Track in Prometheus metrics
        track_database_query(
            operation="select" if "SELECT" in sql_text.upper() else "other",
            table=analysis["table_names"][0] if analysis["table_names"] else "unknown",
            duration=execution_time_ms / 1000,
            success=error is None
        )
        
        return metrics
    
    def _create_query_hash(self, sql_text: str) -> str:
        """Create a hash for query pattern matching"""
        import hashlib
        import re
        
        # Normalize the query for pattern matching
        normalized = sql_text.upper()
        
        # Replace parameter placeholders with generic markers
        normalized = re.sub(r'\$\d+', '$PARAM', normalized)
        normalized = re.sub(r"'[^']*'", "'VALUE'", normalized)
        normalized = re.sub(r'\d+', 'NUMBER', normalized)
        
        # Remove extra whitespace
        normalized = ' '.join(normalized.split())
        
        return hashlib.md5(normalized.encode()).hexdigest()[:16]
    
    def detect_n1_queries(self, time_window_minutes: int = 5) -> List[N1QueryDetection]:
        """Detect N+1 query patterns in recent query history"""
        cutoff_time = datetime.utcnow() - timedelta(minutes=time_window_minutes)
        recent_queries = [q for q in self.query_history if q.timestamp > cutoff_time]
        
        # Group queries by pattern
        pattern_groups = defaultdict(list)
        for query in recent_queries:
            pattern_groups[query.query_hash].append(query)
        
        n1_detections = []
        
        # Look for patterns that might indicate N+1 queries
        for pattern_hash, queries in pattern_groups.items():
            if len(queries) > 10:  # Threshold for potential N+1
                # Check if these are similar queries executed many times
                first_query = queries[0]
                if any(table in ["guests", "messages", "conversations"] for table in first_query.table_names):
                    total_time = sum(q.execution_time_ms for q in queries)
                    
                    detection = N1QueryDetection(
                        parent_query="Unknown parent query",
                        child_queries=[first_query.sql_text],
                        execution_count=len(queries),
                        total_time_ms=total_time,
                        suggested_fix=self._suggest_n1_fix(first_query)
                    )
                    
                    n1_detections.append(detection)
        
        self.n1_detections.extend(n1_detections)
        return n1_detections
    
    def _suggest_n1_fix(self, query_metrics: QueryMetrics) -> str:
        """Suggest fixes for N+1 query patterns"""
        if "guests" in query_metrics.table_names:
            return "Use selectinload() or joinedload() to eagerly load guest relationships"
        elif "messages" in query_metrics.table_names:
            return "Use selectinload() to batch load messages for conversations"
        elif "conversations" in query_metrics.table_names:
            return "Use joinedload() to eagerly load conversation data with guests"
        else:
            return "Consider using eager loading or batch queries to reduce query count"
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive query performance summary"""
        if not self.query_history:
            return {"message": "No query data available"}
        
        # Calculate statistics
        total_queries = len(self.query_history)
        slow_query_count = len(self.slow_queries)
        avg_execution_time = sum(q.execution_time_ms for q in self.query_history) / total_queries
        
        # Most frequent queries
        most_frequent = sorted(
            self.query_frequency.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        # Most accessed tables
        most_accessed_tables = sorted(
            self.table_access_patterns.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            "total_queries": total_queries,
            "slow_queries": slow_query_count,
            "slow_query_percentage": (slow_query_count / total_queries) * 100,
            "avg_execution_time_ms": avg_execution_time,
            "most_frequent_queries": most_frequent,
            "most_accessed_tables": most_accessed_tables,
            "n1_detections": len(self.n1_detections),
            "optimization_opportunities": self._identify_optimization_opportunities()
        }
    
    def _identify_optimization_opportunities(self) -> List[str]:
        """Identify optimization opportunities based on query patterns"""
        opportunities = []
        
        # Check for frequently slow queries
        slow_patterns = defaultdict(int)
        for query in self.slow_queries:
            slow_patterns[query.query_hash] += 1
        
        for pattern_hash, count in slow_patterns.items():
            if count > 5:
                opportunities.append(f"Query pattern {pattern_hash[:8]} is frequently slow ({count} times)")
        
        # Check for high table access without proper indexing hints
        for table, access_count in self.table_access_patterns.items():
            if access_count > 100:
                opportunities.append(f"Table '{table}' is heavily accessed ({access_count} times) - verify indexing")
        
        return opportunities


# Global query analyzer instance
query_analyzer = QueryAnalyzer()


def get_query_analyzer() -> QueryAnalyzer:
    """Get the global query analyzer instance"""
    return query_analyzer


@asynccontextmanager
async def optimized_query_execution(session: AsyncSession, query: Union[str, Select]):
    """Context manager for optimized query execution with automatic tracking"""
    start_time = time.time()
    sql_text = str(query) if hasattr(query, '__str__') else query
    error = None
    row_count = 0

    try:
        if isinstance(query, str):
            result = await session.execute(text(query))
        else:
            result = await session.execute(query)

        # Try to get row count if possible
        try:
            if hasattr(result, 'rowcount'):
                row_count = result.rowcount
            elif hasattr(result, 'fetchall'):
                rows = result.fetchall()
                row_count = len(rows)
                # Return the rows for the caller
                result._rows = rows
        except:
            pass

        yield result

    except Exception as e:
        error = str(e)
        raise

    finally:
        execution_time = (time.time() - start_time) * 1000
        await query_analyzer.track_query_execution(
            sql_text=sql_text,
            execution_time_ms=execution_time,
            row_count=row_count,
            error=error
        )


class EagerLoadingHelper:
    """Helper class for preventing N+1 queries with eager loading"""

    @staticmethod
    def load_conversations_with_guests(query):
        """Load conversations with guest data to prevent N+1"""
        return query.options(
            joinedload("guest"),
            selectinload("messages").options(
                joinedload("sentiment_analysis")
            )
        )

    @staticmethod
    def load_guests_with_conversations(query):
        """Load guests with conversation data to prevent N+1"""
        return query.options(
            selectinload("conversations").options(
                selectinload("messages")
            ),
            selectinload("staff_notifications")
        )

    @staticmethod
    def load_hotels_with_related_data(query):
        """Load hotels with commonly accessed related data"""
        return query.options(
            selectinload("guests").options(
                selectinload("conversations")
            ),
            selectinload("triggers"),
            selectinload("staff_notifications")
        )

    @staticmethod
    def load_messages_with_context(query):
        """Load messages with full context to prevent N+1"""
        return query.options(
            joinedload("conversation").options(
                joinedload("guest"),
                joinedload("hotel")
            ),
            selectinload("sentiment_analysis")
        )
