"""
Memory usage optimization utilities for WhatsApp Hotel Bot
Provides memory profiling, garbage collection tuning, and memory leak detection
"""

import gc
import sys
import psutil
import tracemalloc
import weakref
import threading
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from contextlib import contextmanager

import structlog
from app.core.logging import get_logger
from app.core.metrics import track_memory_usage

logger = get_logger(__name__)


@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: datetime = field(default_factory=datetime.utcnow)
    total_memory_mb: float = 0.0
    available_memory_mb: float = 0.0
    process_memory_mb: float = 0.0
    process_memory_percent: float = 0.0
    gc_objects: int = 0
    gc_collections: Dict[int, int] = field(default_factory=dict)
    tracemalloc_current_mb: float = 0.0
    tracemalloc_peak_mb: float = 0.0


@dataclass
class MemoryLeak:
    """Memory leak detection result"""
    object_type: str
    count: int
    size_mb: float
    growth_rate: float
    first_seen: datetime
    last_seen: datetime
    stack_trace: Optional[str] = None


class MemoryProfiler:
    """Memory profiling and monitoring"""
    
    def __init__(self, enable_tracemalloc: bool = True):
        self.enable_tracemalloc = enable_tracemalloc
        self.logger = logger.bind(component="memory_profiler")
        
        # Memory tracking
        self.snapshots: deque = deque(maxlen=1000)
        self.object_tracking: Dict[type, List[int]] = defaultdict(list)
        self.leak_candidates: Dict[str, MemoryLeak] = {}
        
        # Configuration
        self.snapshot_interval = 60  # seconds
        self.leak_detection_threshold = 1.5  # MB growth
        self.monitoring_enabled = False
        
        # Initialize tracemalloc if enabled
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start()
            self.logger.info("Memory tracing started")
    
    def take_snapshot(self) -> MemorySnapshot:
        """Take a memory usage snapshot"""
        try:
            # System memory info
            memory_info = psutil.virtual_memory()
            
            # Process memory info
            process = psutil.Process()
            process_memory = process.memory_info()
            
            # Garbage collection info
            gc_stats = {}
            for i in range(3):  # GC generations 0, 1, 2
                gc_stats[i] = gc.get_count()[i]
            
            # Tracemalloc info
            tracemalloc_current = 0.0
            tracemalloc_peak = 0.0
            if self.enable_tracemalloc and tracemalloc.is_tracing():
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # Convert to MB
                tracemalloc_peak = peak / 1024 / 1024
            
            snapshot = MemorySnapshot(
                total_memory_mb=memory_info.total / 1024 / 1024,
                available_memory_mb=memory_info.available / 1024 / 1024,
                process_memory_mb=process_memory.rss / 1024 / 1024,
                process_memory_percent=memory_info.percent,
                gc_objects=len(gc.get_objects()),
                gc_collections=gc_stats,
                tracemalloc_current_mb=tracemalloc_current,
                tracemalloc_peak_mb=tracemalloc_peak
            )
            
            self.snapshots.append(snapshot)
            
            # Track memory usage in metrics
            track_memory_usage(
                snapshot.process_memory_mb,
                snapshot.process_memory_percent,
                snapshot.gc_objects
            )
            
            return snapshot
            
        except Exception as e:
            self.logger.error("Failed to take memory snapshot", error=str(e))
            return MemorySnapshot()
    
    def detect_memory_leaks(self, window_minutes: int = 30) -> List[MemoryLeak]:
        """Detect potential memory leaks"""
        if len(self.snapshots) < 2:
            return []
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=window_minutes)
        recent_snapshots = [s for s in self.snapshots if s.timestamp > cutoff_time]
        
        if len(recent_snapshots) < 2:
            return []
        
        # Analyze memory growth
        first_snapshot = recent_snapshots[0]
        last_snapshot = recent_snapshots[-1]
        
        memory_growth = last_snapshot.process_memory_mb - first_snapshot.process_memory_mb
        time_diff = (last_snapshot.timestamp - first_snapshot.timestamp).total_seconds() / 60  # minutes
        
        leaks = []
        
        # Check for significant memory growth
        if memory_growth > self.leak_detection_threshold and time_diff > 0:
            growth_rate = memory_growth / time_diff  # MB per minute
            
            # Get top memory consumers if tracemalloc is enabled
            if self.enable_tracemalloc and tracemalloc.is_tracing():
                top_stats = tracemalloc.take_snapshot().statistics('lineno')
                
                for stat in top_stats[:10]:  # Top 10 memory consumers
                    leak = MemoryLeak(
                        object_type=f"{stat.traceback.format()[-1] if stat.traceback else 'unknown'}",
                        count=stat.count,
                        size_mb=stat.size / 1024 / 1024,
                        growth_rate=growth_rate,
                        first_seen=first_snapshot.timestamp,
                        last_seen=last_snapshot.timestamp,
                        stack_trace='\n'.join(stat.traceback.format()) if stat.traceback else None
                    )
                    leaks.append(leak)
            else:
                # Generic memory leak detection
                leak = MemoryLeak(
                    object_type="unknown",
                    count=last_snapshot.gc_objects - first_snapshot.gc_objects,
                    size_mb=memory_growth,
                    growth_rate=growth_rate,
                    first_seen=first_snapshot.timestamp,
                    last_seen=last_snapshot.timestamp
                )
                leaks.append(leak)
        
        return leaks
    
    def get_top_memory_consumers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top memory consuming objects"""
        if not self.enable_tracemalloc or not tracemalloc.is_tracing():
            return []
        
        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            consumers = []
            for stat in top_stats[:limit]:
                consumers.append({
                    "size_mb": stat.size / 1024 / 1024,
                    "count": stat.count,
                    "average_size": stat.size / stat.count if stat.count > 0 else 0,
                    "traceback": stat.traceback.format() if stat.traceback else ["unknown"]
                })
            
            return consumers
            
        except Exception as e:
            self.logger.error("Failed to get memory consumers", error=str(e))
            return []
    
    def start_monitoring(self, interval_seconds: int = 60):
        """Start continuous memory monitoring"""
        self.snapshot_interval = interval_seconds
        self.monitoring_enabled = True
        
        def monitor_loop():
            while self.monitoring_enabled:
                try:
                    snapshot = self.take_snapshot()
                    
                    # Check for memory leaks
                    leaks = self.detect_memory_leaks()
                    if leaks:
                        self.logger.warning("Potential memory leaks detected", 
                                          leak_count=len(leaks))
                        for leak in leaks:
                            self.logger.warning("Memory leak candidate",
                                              object_type=leak.object_type,
                                              size_mb=leak.size_mb,
                                              growth_rate=leak.growth_rate)
                    
                    # Log high memory usage
                    if snapshot.process_memory_percent > 80:
                        self.logger.warning("High memory usage detected",
                                          memory_percent=snapshot.process_memory_percent,
                                          memory_mb=snapshot.process_memory_mb)
                    
                except Exception as e:
                    self.logger.error("Error in memory monitoring", error=str(e))
                
                time.sleep(self.snapshot_interval)
        
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()
        
        self.logger.info("Memory monitoring started", interval=interval_seconds)
    
    def stop_monitoring(self):
        """Stop memory monitoring"""
        self.monitoring_enabled = False
        self.logger.info("Memory monitoring stopped")
    
    def get_memory_report(self) -> Dict[str, Any]:
        """Get comprehensive memory report"""
        if not self.snapshots:
            return {"error": "No memory snapshots available"}
        
        latest_snapshot = self.snapshots[-1]
        
        # Calculate trends if we have enough data
        trends = {}
        if len(self.snapshots) >= 10:
            recent_snapshots = list(self.snapshots)[-10:]
            memory_values = [s.process_memory_mb for s in recent_snapshots]
            
            trends = {
                "memory_trend": "increasing" if memory_values[-1] > memory_values[0] else "decreasing",
                "avg_memory_mb": sum(memory_values) / len(memory_values),
                "max_memory_mb": max(memory_values),
                "min_memory_mb": min(memory_values)
            }
        
        # Get memory leaks
        leaks = self.detect_memory_leaks()
        
        # Get top consumers
        top_consumers = self.get_top_memory_consumers()
        
        return {
            "current_snapshot": {
                "timestamp": latest_snapshot.timestamp.isoformat(),
                "process_memory_mb": latest_snapshot.process_memory_mb,
                "memory_percent": latest_snapshot.process_memory_percent,
                "gc_objects": latest_snapshot.gc_objects,
                "tracemalloc_current_mb": latest_snapshot.tracemalloc_current_mb,
                "tracemalloc_peak_mb": latest_snapshot.tracemalloc_peak_mb
            },
            "trends": trends,
            "memory_leaks": [
                {
                    "object_type": leak.object_type,
                    "size_mb": leak.size_mb,
                    "growth_rate": leak.growth_rate,
                    "duration_minutes": (leak.last_seen - leak.first_seen).total_seconds() / 60
                }
                for leak in leaks
            ],
            "top_consumers": top_consumers,
            "gc_stats": {
                "collections": latest_snapshot.gc_collections,
                "thresholds": gc.get_threshold(),
                "counts": gc.get_count()
            }
        }


class GarbageCollectionOptimizer:
    """Garbage collection optimization"""
    
    def __init__(self):
        self.logger = logger.bind(component="gc_optimizer")
        self.original_thresholds = gc.get_threshold()
        self.collection_stats = defaultdict(int)
        
    def optimize_gc_settings(self, 
                           generation_0_threshold: int = 2000,
                           generation_1_threshold: int = 20,
                           generation_2_threshold: int = 20):
        """Optimize garbage collection thresholds"""
        try:
            # Set new thresholds
            gc.set_threshold(generation_0_threshold, generation_1_threshold, generation_2_threshold)
            
            self.logger.info("GC thresholds optimized",
                           old_thresholds=self.original_thresholds,
                           new_thresholds=(generation_0_threshold, generation_1_threshold, generation_2_threshold))
            
        except Exception as e:
            self.logger.error("Failed to optimize GC settings", error=str(e))
    
    def force_collection(self) -> Dict[str, int]:
        """Force garbage collection and return statistics"""
        try:
            collected = {}
            for generation in range(3):
                collected[f"generation_{generation}"] = gc.collect(generation)
                self.collection_stats[generation] += 1
            
            self.logger.debug("Forced garbage collection", collected=collected)
            return collected
            
        except Exception as e:
            self.logger.error("Failed to force garbage collection", error=str(e))
            return {}
    
    def get_gc_stats(self) -> Dict[str, Any]:
        """Get garbage collection statistics"""
        return {
            "thresholds": gc.get_threshold(),
            "counts": gc.get_count(),
            "stats": gc.get_stats(),
            "collection_stats": dict(self.collection_stats),
            "is_enabled": gc.isenabled()
        }
    
    def restore_original_settings(self):
        """Restore original GC settings"""
        gc.set_threshold(*self.original_thresholds)
        self.logger.info("GC settings restored to original", thresholds=self.original_thresholds)


@contextmanager
def memory_profiling(name: str):
    """Context manager for memory profiling"""
    profiler = get_memory_profiler()
    
    start_snapshot = profiler.take_snapshot()
    start_time = time.time()
    
    try:
        yield
    finally:
        end_snapshot = profiler.take_snapshot()
        duration = time.time() - start_time
        
        memory_diff = end_snapshot.process_memory_mb - start_snapshot.process_memory_mb
        
        logger.info("Memory profiling completed",
                   operation=name,
                   duration_seconds=duration,
                   memory_diff_mb=memory_diff,
                   start_memory_mb=start_snapshot.process_memory_mb,
                   end_memory_mb=end_snapshot.process_memory_mb)


# Global instances
memory_profiler: Optional[MemoryProfiler] = None
gc_optimizer: Optional[GarbageCollectionOptimizer] = None


def get_memory_profiler() -> MemoryProfiler:
    """Get the global memory profiler instance"""
    global memory_profiler
    if memory_profiler is None:
        memory_profiler = MemoryProfiler()
    return memory_profiler


def get_gc_optimizer() -> GarbageCollectionOptimizer:
    """Get the global GC optimizer instance"""
    global gc_optimizer
    if gc_optimizer is None:
        gc_optimizer = GarbageCollectionOptimizer()
    return gc_optimizer


def initialize_memory_optimization():
    """Initialize memory optimization components"""
    profiler = get_memory_profiler()
    optimizer = get_gc_optimizer()
    
    # Start memory monitoring
    profiler.start_monitoring()
    
    # Optimize GC settings for the application
    optimizer.optimize_gc_settings()
    
    logger.info("Memory optimization initialized")
