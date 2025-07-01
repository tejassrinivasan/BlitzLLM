"""
Metrics collection and monitoring for BlitzAgent.

This module provides comprehensive metrics collection using Prometheus
and structured logging for monitoring agent performance.
"""

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from threading import Lock
import threading

import structlog
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, Info,
    CollectorRegistry, REGISTRY, generate_latest,
    start_http_server
)


logger = structlog.get_logger(__name__)


@dataclass
class MetricsSummary:
    """Summary of current metrics."""
    total_queries: int
    total_errors: int
    avg_response_time_ms: float
    success_rate: float
    total_tokens_used: int
    avg_tokens_per_query: float
    active_sessions: int
    memory_usage_mb: float
    uptime_seconds: float
    top_tools: List[Dict[str, Any]]
    recent_errors: List[str]


class MetricsCollector:
    """
    Comprehensive metrics collector for BlitzAgent.
    
    Collects and exposes metrics for:
    - Query performance
    - Error rates
    - Token usage
    - Memory usage
    - Tool usage
    - Response times
    """
    
    def __init__(self, enabled: bool = True, registry: CollectorRegistry = None):
        """Initialize metrics collector."""
        self.enabled = enabled
        self.registry = registry or REGISTRY
        self.start_time = time.time()
        
        # Thread safety
        self._lock = Lock()
        
        # In-memory metrics for fast access
        self._query_count = 0
        self._error_count = 0
        self._response_times = deque(maxlen=1000)  # Last 1000 response times
        self._token_usage = deque(maxlen=1000)  # Last 1000 token usages
        self._tool_usage = defaultdict(int)
        self._recent_errors = deque(maxlen=50)  # Last 50 errors
        self._active_sessions = set()
        
        if self.enabled:
            self._setup_prometheus_metrics()
        
        logger.info("Metrics collector initialized", enabled=enabled)
    
    def _setup_prometheus_metrics(self) -> None:
        """Setup Prometheus metrics."""
        # Counters
        self.query_counter = Counter(
            'blitzagent_queries_total',
            'Total number of queries processed',
            registry=self.registry
        )
        
        self.error_counter = Counter(
            'blitzagent_errors_total',
            'Total number of errors',
            ['error_type'],
            registry=self.registry
        )
        
        self.token_counter = Counter(
            'blitzagent_tokens_total',
            'Total number of tokens used',
            ['token_type'],  # input, output
            registry=self.registry
        )
        
        self.tool_usage_counter = Counter(
            'blitzagent_tool_usage_total',
            'Total tool usage by tool name',
            ['tool_name'],
            registry=self.registry
        )
        
        # Histograms
        self.response_time_histogram = Histogram(
            'blitzagent_response_time_seconds',
            'Response time distribution',
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0],
            registry=self.registry
        )
        
        self.token_usage_histogram = Histogram(
            'blitzagent_token_usage',
            'Token usage distribution per query',
            buckets=[10, 50, 100, 500, 1000, 2000, 4000, 8000],
            registry=self.registry
        )
        
        # Gauges
        self.active_sessions_gauge = Gauge(
            'blitzagent_active_sessions',
            'Number of active sessions',
            registry=self.registry
        )
        
        self.memory_usage_gauge = Gauge(
            'blitzagent_memory_usage_bytes',
            'Memory usage in bytes',
            registry=self.registry
        )
        
        self.database_connections_gauge = Gauge(
            'blitzagent_database_connections',
            'Number of active database connections',
            registry=self.registry
        )
        
        # Summaries
        self.response_time_summary = Summary(
            'blitzagent_response_time_summary',
            'Response time summary statistics',
            registry=self.registry
        )
        
        # Info metrics
        self.info_metric = Info(
            'blitzagent_info',
            'BlitzAgent information',
            registry=self.registry
        )
        
        # Set info metric
        self.info_metric.info({
            'version': '0.1.0',
            'model': 'gemini-2.5-pro-reasoning',
            'features': 'streaming,memory,mcp,structured_output'
        })
    
    def increment_query_count(self) -> None:
        """Increment query counter."""
        if not self.enabled:
            return
        
        with self._lock:
            self._query_count += 1
        
        if hasattr(self, 'query_counter'):
            self.query_counter.inc()
    
    def increment_error_count(self, error_type: str = "general") -> None:
        """Increment error counter."""
        if not self.enabled:
            return
        
        with self._lock:
            self._error_count += 1
            self._recent_errors.append(f"{datetime.utcnow().isoformat()}: {error_type}")
        
        if hasattr(self, 'error_counter'):
            self.error_counter.labels(error_type=error_type).inc()
    
    def record_response_time(self, duration_ms: float) -> None:
        """Record response time."""
        if not self.enabled:
            return
        
        duration_seconds = duration_ms / 1000.0
        
        with self._lock:
            self._response_times.append(duration_ms)
        
        if hasattr(self, 'response_time_histogram'):
            self.response_time_histogram.observe(duration_seconds)
        
        if hasattr(self, 'response_time_summary'):
            self.response_time_summary.observe(duration_seconds)
    
    def record_token_usage(self, token_usage: Dict[str, int]) -> None:
        """Record token usage."""
        if not self.enabled:
            return
        
        total_tokens = sum(token_usage.values())
        
        with self._lock:
            self._token_usage.append(total_tokens)
        
        if hasattr(self, 'token_counter'):
            for token_type, count in token_usage.items():
                self.token_counter.labels(token_type=token_type).inc(count)
        
        if hasattr(self, 'token_usage_histogram'):
            self.token_usage_histogram.observe(total_tokens)
    
    def increment_tool_usage(self, tool_name: str) -> None:
        """Increment tool usage counter."""
        if not self.enabled:
            return
        
        with self._lock:
            self._tool_usage[tool_name] += 1
        
        if hasattr(self, 'tool_usage_counter'):
            self.tool_usage_counter.labels(tool_name=tool_name).inc()
    
    def record_initialization_time(self, duration_ms: float) -> None:
        """Record initialization time."""
        if not self.enabled:
            return
        
        logger.info("Agent initialization completed", duration_ms=duration_ms)
    
    def add_active_session(self, session_id: str) -> None:
        """Add an active session."""
        if not self.enabled:
            return
        
        with self._lock:
            self._active_sessions.add(session_id)
        
        if hasattr(self, 'active_sessions_gauge'):
            self.active_sessions_gauge.set(len(self._active_sessions))
    
    def remove_active_session(self, session_id: str) -> None:
        """Remove an active session."""
        if not self.enabled:
            return
        
        with self._lock:
            self._active_sessions.discard(session_id)
        
        if hasattr(self, 'active_sessions_gauge'):
            self.active_sessions_gauge.set(len(self._active_sessions))
    
    def update_memory_usage(self, usage_bytes: float) -> None:
        """Update memory usage metric."""
        if not self.enabled:
            return
        
        if hasattr(self, 'memory_usage_gauge'):
            self.memory_usage_gauge.set(usage_bytes)
    
    def update_database_connections(self, connection_count: int) -> None:
        """Update database connections metric."""
        if not self.enabled:
            return
        
        if hasattr(self, 'database_connections_gauge'):
            self.database_connections_gauge.set(connection_count)
    
    def get_metrics(self) -> MetricsSummary:
        """Get current metrics summary."""
        with self._lock:
            # Calculate averages
            avg_response_time = (
                sum(self._response_times) / len(self._response_times)
                if self._response_times else 0.0
            )
            
            avg_tokens = (
                sum(self._token_usage) / len(self._token_usage)
                if self._token_usage else 0.0
            )
            
            success_rate = (
                (self._query_count - self._error_count) / self._query_count
                if self._query_count > 0 else 1.0
            )
            
            # Top tools
            top_tools = [
                {"tool": tool, "usage": count}
                for tool, count in sorted(
                    self._tool_usage.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:10]
            ]
            
            # Recent errors
            recent_errors = list(self._recent_errors)[-10:]  # Last 10 errors
            
            return MetricsSummary(
                total_queries=self._query_count,
                total_errors=self._error_count,
                avg_response_time_ms=avg_response_time,
                success_rate=success_rate,
                total_tokens_used=sum(self._token_usage),
                avg_tokens_per_query=avg_tokens,
                active_sessions=len(self._active_sessions),
                memory_usage_mb=0.0,  # Would be updated by external monitoring
                uptime_seconds=time.time() - self.start_time,
                top_tools=top_tools,
                recent_errors=recent_errors
            )
    
    def get_prometheus_metrics(self) -> str:
        """Get Prometheus metrics in text format."""
        if not self.enabled:
            return ""
        
        return generate_latest(self.registry).decode('utf-8')
    
    def start_metrics_server(self, port: int = 9090) -> None:
        """Start Prometheus metrics HTTP server."""
        if not self.enabled:
            logger.warning("Metrics collection disabled, not starting server")
            return
        
        try:
            start_http_server(port, registry=self.registry)
            logger.info("Metrics server started", port=port)
        except Exception as e:
            logger.error("Failed to start metrics server", error=str(e), port=port)
            raise
    
    def export_metrics_to_dict(self) -> Dict[str, Any]:
        """Export all metrics to a dictionary."""
        summary = self.get_metrics()
        return {
            "summary": asdict(summary),
            "detailed": {
                "response_times": list(self._response_times),
                "token_usage": list(self._token_usage),
                "tool_usage": dict(self._tool_usage),
                "active_sessions": list(self._active_sessions),
                "recent_errors": list(self._recent_errors)
            },
            "metadata": {
                "collection_enabled": self.enabled,
                "start_time": self.start_time,
                "current_time": time.time()
            }
        }
    
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        with self._lock:
            self._query_count = 0
            self._error_count = 0
            self._response_times.clear()
            self._token_usage.clear()
            self._tool_usage.clear()
            self._recent_errors.clear()
            self._active_sessions.clear()
        
        logger.info("Metrics reset")


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None
_metrics_lock = Lock()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    
    if _metrics_collector is None:
        with _metrics_lock:
            if _metrics_collector is None:
                _metrics_collector = MetricsCollector()
    
    return _metrics_collector


def configure_metrics(
    enabled: bool = True,
    registry: Optional[CollectorRegistry] = None
) -> MetricsCollector:
    """Configure the global metrics collector."""
    global _metrics_collector
    
    with _metrics_lock:
        _metrics_collector = MetricsCollector(enabled=enabled, registry=registry)
    
    return _metrics_collector


def get_metrics() -> MetricsSummary:
    """Get current metrics summary."""
    collector = get_metrics_collector()
    return collector.get_metrics()


class MetricsMiddleware:
    """Middleware for automatic metrics collection."""
    
    def __init__(self, collector: Optional[MetricsCollector] = None):
        """Initialize metrics middleware."""
        self.collector = collector or get_metrics_collector()
    
    async def __call__(self, request, call_next):
        """Process request and collect metrics."""
        start_time = time.time()
        session_id = request.headers.get('X-Session-ID')
        
        if session_id:
            self.collector.add_active_session(session_id)
        
        try:
            response = await call_next(request)
            
            # Record success metrics
            duration_ms = (time.time() - start_time) * 1000
            self.collector.record_response_time(duration_ms)
            
            return response
            
        except Exception as e:
            # Record error metrics
            self.collector.increment_error_count(type(e).__name__)
            raise
        
        finally:
            if session_id:
                self.collector.remove_active_session(session_id)


class PerformanceMonitor:
    """Context manager for monitoring performance."""
    
    def __init__(
        self,
        name: str,
        collector: Optional[MetricsCollector] = None,
        log_result: bool = True
    ):
        """Initialize performance monitor."""
        self.name = name
        self.collector = collector or get_metrics_collector()
        self.log_result = log_result
        self.start_time = None
    
    def __enter__(self):
        """Start monitoring."""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """End monitoring and record metrics."""
        if self.start_time is None:
            return
        
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is None:
            # Success
            self.collector.record_response_time(duration_ms)
            if self.log_result:
                logger.info(
                    "Performance measurement",
                    operation=self.name,
                    duration_ms=duration_ms,
                    status="success"
                )
        else:
            # Error
            self.collector.increment_error_count(exc_type.__name__)
            if self.log_result:
                logger.error(
                    "Performance measurement",
                    operation=self.name,
                    duration_ms=duration_ms,
                    status="error",
                    error=str(exc_val)
                )


# Decorator for automatic performance monitoring
def monitor_performance(name: Optional[str] = None, log_result: bool = True):
    """Decorator for monitoring function performance."""
    def decorator(func):
        operation_name = name or f"{func.__module__}.{func.__name__}"
        
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                with PerformanceMonitor(operation_name, log_result=log_result):
                    return await func(*args, **kwargs)
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                with PerformanceMonitor(operation_name, log_result=log_result):
                    return func(*args, **kwargs)
            return sync_wrapper
    
    return decorator 