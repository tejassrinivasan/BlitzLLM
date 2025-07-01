"""
Performance evaluation for BlitzAgent measuring runtime and memory footprint.

This module provides comprehensive performance testing including latency measurement,
memory profiling, and resource utilization tracking for agent operations.
"""

import asyncio
import time
import psutil
import tracemalloc
from typing import Optional, List, Dict, Any, Callable, Awaitable
from dataclasses import dataclass
from datetime import datetime
import statistics
import gc
from concurrent.futures import ThreadPoolExecutor

from agno.eval.perf import PerfEval
from pydantic import BaseModel

from ..agent import BlitzAgent
from ..config import Config
from ..agent_factory import RuntimeContext, RuntimeMode, ToneStyle


@dataclass
class MemorySnapshot:
    """Memory usage snapshot."""
    
    current: int  # Current memory usage in MB
    peak: int     # Peak memory usage in MB
    rss: int      # Resident Set Size in MB
    vms: int      # Virtual Memory Size in MB
    timestamp: float


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    
    # Timing metrics
    avg_latency: float
    min_latency: float
    max_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    total_time: float
    
    # Memory metrics
    avg_memory_mb: float
    peak_memory_mb: float
    memory_growth_mb: float
    memory_snapshots: List[MemorySnapshot]
    
    # Throughput metrics
    operations_per_second: float
    tokens_per_second: Optional[float] = None
    
    # Reliability metrics
    success_rate: float
    error_count: int
    total_operations: int
    
    # Resource utilization
    avg_cpu_percent: float
    max_cpu_percent: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "avg_latency": self.avg_latency,
            "min_latency": self.min_latency,
            "max_latency": self.max_latency,
            "p50_latency": self.p50_latency,
            "p95_latency": self.p95_latency,
            "p99_latency": self.p99_latency,
            "total_time": self.total_time,
            "avg_memory_mb": self.avg_memory_mb,
            "peak_memory_mb": self.peak_memory_mb,
            "memory_growth_mb": self.memory_growth_mb,
            "operations_per_second": self.operations_per_second,
            "tokens_per_second": self.tokens_per_second,
            "success_rate": self.success_rate,
            "error_count": self.error_count,
            "total_operations": self.total_operations,
            "avg_cpu_percent": self.avg_cpu_percent,
            "max_cpu_percent": self.max_cpu_percent,
            "timestamp": datetime.utcnow().isoformat()
        }


class PerformanceTestCase(BaseModel):
    """Test case for performance evaluation."""
    
    name: str
    input: str
    iterations: int = 5
    warmup_iterations: int = 1
    context: Optional[RuntimeContext] = None
    expected_max_latency: Optional[float] = None  # seconds
    expected_max_memory: Optional[float] = None   # MB


class BlitzPerformanceEval:
    """
    Performance evaluation for BlitzAgent.
    
    Measures latency, memory usage, throughput, and resource utilization
    for various agent operations.
    """
    
    def __init__(
        self,
        agent_config: Optional[Config] = None,
        agent_context: Optional[RuntimeContext] = None,
        enable_memory_profiling: bool = True,
        enable_cpu_monitoring: bool = True,
        sampling_interval: float = 0.1  # seconds
    ):
        """Initialize the performance evaluator."""
        self.agent_config = agent_config or Config()
        self.agent_context = agent_context or RuntimeContext(
            mode=RuntimeMode.INSIGHT,
            tone=ToneStyle.ANALYTICAL
        )
        self.enable_memory_profiling = enable_memory_profiling
        self.enable_cpu_monitoring = enable_cpu_monitoring
        self.sampling_interval = sampling_interval
        
        # Process handle for monitoring
        self.process = psutil.Process()
    
    async def evaluate_single(
        self,
        test_case: PerformanceTestCase,
        agent: Optional[BlitzAgent] = None
    ) -> PerformanceMetrics:
        """Evaluate performance for a single test case."""
        
        # Create agent if not provided
        agent_created = False
        if agent is None:
            agent = BlitzAgent(
                config=self.agent_config, 
                context=test_case.context or self.agent_context
            )
            await agent.initialize()
            agent_created = True
        
        try:
            return await self._run_performance_test(agent, test_case)
        finally:
            if agent_created and agent:
                await agent.cleanup()
    
    async def _run_performance_test(
        self,
        agent: BlitzAgent,
        test_case: PerformanceTestCase
    ) -> PerformanceMetrics:
        """Run the actual performance test."""
        
        # Start memory tracking
        if self.enable_memory_profiling:
            tracemalloc.start()
            initial_memory = self._get_memory_usage()
        
        # Initialize metrics tracking
        latencies = []
        memory_snapshots = []
        cpu_percentages = []
        error_count = 0
        token_counts = []
        
        # Start monitoring task
        monitoring_task = None
        if self.enable_cpu_monitoring or self.enable_memory_profiling:
            monitoring_task = asyncio.create_task(
                self._monitor_resources(memory_snapshots, cpu_percentages)
            )
        
        # Warmup runs
        for _ in range(test_case.warmup_iterations):
            try:
                await agent.run(
                    message=test_case.input,
                    user_id="perf_warmup",
                    session_id="perf_warmup",
                    stream=False
                )
            except Exception:
                pass  # Ignore warmup errors
        
        # Force garbage collection before actual test
        gc.collect()
        
        # Actual performance test
        start_time = time.time()
        
        for i in range(test_case.iterations):
            iteration_start = time.time()
            
            try:
                response = await agent.run(
                    message=test_case.input,
                    user_id=f"perf_user_{i}",
                    session_id=f"perf_session_{i}",
                    stream=False
                )
                
                iteration_time = time.time() - iteration_start
                latencies.append(iteration_time)
                
                # Track token usage if available
                if hasattr(response, 'token_usage') and response.token_usage:
                    total_tokens = response.token_usage.get('total_tokens', 0)
                    if total_tokens > 0:
                        token_counts.append(total_tokens / iteration_time)
                
            except Exception as e:
                error_count += 1
                latencies.append(time.time() - iteration_start)
                print(f"Error in iteration {i}: {str(e)}")
        
        total_time = time.time() - start_time
        
        # Stop monitoring
        if monitoring_task:
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
        
        # Calculate memory metrics
        if self.enable_memory_profiling:
            final_memory = self._get_memory_usage()
            tracemalloc.stop()
            memory_growth = final_memory.current - initial_memory.current
        else:
            memory_growth = 0.0
            final_memory = self._get_memory_usage()
        
        # Calculate performance metrics
        return self._calculate_metrics(
            latencies=latencies,
            memory_snapshots=memory_snapshots,
            cpu_percentages=cpu_percentages,
            total_time=total_time,
            error_count=error_count,
            total_operations=test_case.iterations,
            memory_growth=memory_growth,
            token_counts=token_counts
        )
    
    async def _monitor_resources(
        self,
        memory_snapshots: List[MemorySnapshot],
        cpu_percentages: List[float]
    ):
        """Monitor CPU and memory usage during test execution."""
        try:
            while True:
                if self.enable_memory_profiling:
                    memory_snapshots.append(self._get_memory_usage())
                
                if self.enable_cpu_monitoring:
                    cpu_percent = self.process.cpu_percent()
                    if cpu_percent > 0:  # Skip initial 0 readings
                        cpu_percentages.append(cpu_percent)
                
                await asyncio.sleep(self.sampling_interval)
        except asyncio.CancelledError:
            pass
    
    def _get_memory_usage(self) -> MemorySnapshot:
        """Get current memory usage snapshot."""
        memory_info = self.process.memory_info()
        
        # Get tracemalloc info if available
        current_mb = 0
        peak_mb = 0
        
        if tracemalloc.is_tracing():
            current, peak = tracemalloc.get_traced_memory()
            current_mb = current / (1024 * 1024)
            peak_mb = peak / (1024 * 1024)
        
        return MemorySnapshot(
            current=int(current_mb),
            peak=int(peak_mb),
            rss=int(memory_info.rss / (1024 * 1024)),  # Convert to MB
            vms=int(memory_info.vms / (1024 * 1024)),  # Convert to MB
            timestamp=time.time()
        )
    
    def _calculate_metrics(
        self,
        latencies: List[float],
        memory_snapshots: List[MemorySnapshot],
        cpu_percentages: List[float],
        total_time: float,
        error_count: int,
        total_operations: int,
        memory_growth: float,
        token_counts: List[float]
    ) -> PerformanceMetrics:
        """Calculate comprehensive performance metrics."""
        
        # Latency metrics
        if latencies:
            sorted_latencies = sorted(latencies)
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p50_latency = statistics.median(latencies)
            p95_latency = sorted_latencies[int(0.95 * len(sorted_latencies))]
            p99_latency = sorted_latencies[int(0.99 * len(sorted_latencies))]
        else:
            avg_latency = min_latency = max_latency = p50_latency = p95_latency = p99_latency = 0.0
        
        # Memory metrics
        if memory_snapshots:
            avg_memory = statistics.mean([s.rss for s in memory_snapshots])
            peak_memory = max([s.rss for s in memory_snapshots])
        else:
            avg_memory = peak_memory = 0.0
        
        # CPU metrics
        if cpu_percentages:
            avg_cpu = statistics.mean(cpu_percentages)
            max_cpu = max(cpu_percentages)
        else:
            avg_cpu = max_cpu = 0.0
        
        # Throughput metrics
        operations_per_second = total_operations / total_time if total_time > 0 else 0.0
        tokens_per_second = statistics.mean(token_counts) if token_counts else None
        
        # Reliability metrics
        success_rate = (total_operations - error_count) / total_operations if total_operations > 0 else 0.0
        
        return PerformanceMetrics(
            avg_latency=avg_latency,
            min_latency=min_latency,
            max_latency=max_latency,
            p50_latency=p50_latency,
            p95_latency=p95_latency,
            p99_latency=p99_latency,
            total_time=total_time,
            avg_memory_mb=avg_memory,
            peak_memory_mb=peak_memory,
            memory_growth_mb=memory_growth,
            memory_snapshots=memory_snapshots,
            operations_per_second=operations_per_second,
            tokens_per_second=tokens_per_second,
            success_rate=success_rate,
            error_count=error_count,
            total_operations=total_operations,
            avg_cpu_percent=avg_cpu,
            max_cpu_percent=max_cpu
        )
    
    async def evaluate_batch(
        self,
        test_cases: List[PerformanceTestCase],
        agent: Optional[BlitzAgent] = None
    ) -> List[PerformanceMetrics]:
        """Evaluate multiple performance test cases."""
        results = []
        
        # Create agent once for all evaluations
        agent_created = False
        if agent is None:
            agent = BlitzAgent(config=self.agent_config, context=self.agent_context)
            await agent.initialize()
            agent_created = True
        
        try:
            for test_case in test_cases:
                result = await self.evaluate_single(test_case, agent)
                results.append(result)
        finally:
            if agent_created and agent:
                await agent.cleanup()
        
        return results
    
    def create_test_cases(self) -> List[PerformanceTestCase]:
        """Create default performance test cases."""
        return [
            PerformanceTestCase(
                name="Simple Query",
                input="What is LeBron James' career scoring average?",
                iterations=10,
                warmup_iterations=2,
                expected_max_latency=5.0,  # 5 seconds max
                expected_max_memory=500.0  # 500 MB max
            ),
            PerformanceTestCase(
                name="Complex Analysis", 
                input="Compare the offensive efficiency of all NBA teams this season and identify the top 3 performers with detailed statistics",
                iterations=5,
                warmup_iterations=1,
                expected_max_latency=15.0,  # 15 seconds max
                expected_max_memory=800.0   # 800 MB max
            ),
            PerformanceTestCase(
                name="Historical Comparison",
                input="Compare Michael Jordan's 1996 season to LeBron James' 2013 season across all major statistical categories",
                iterations=3,
                warmup_iterations=1,
                expected_max_latency=10.0,
                expected_max_memory=600.0
            ),
            PerformanceTestCase(
                name="Real-time Data",
                input="What happened in today's NBA games?",
                iterations=8,
                warmup_iterations=1,
                expected_max_latency=8.0,
                expected_max_memory=400.0
            ),
            PerformanceTestCase(
                name="Memory Stress Test",
                input="Analyze all MLB pitchers' performance over the last 5 seasons and rank them by WAR",
                iterations=2,
                warmup_iterations=1,
                expected_max_latency=30.0,
                expected_max_memory=1000.0
            )
        ]
    
    async def benchmark_agent_components(
        self,
        agent: BlitzAgent
    ) -> Dict[str, PerformanceMetrics]:
        """
        Benchmark individual agent components.
        
        Tests performance with and without different components:
        - With/without memory
        - With/without MCP tools
        - Different model configurations
        """
        benchmarks = {}
        
        # Test cases for component benchmarking
        simple_query = "Who won the 2023 NBA Finals?"
        
        # Base configuration
        base_case = PerformanceTestCase(
            name="Base Configuration",
            input=simple_query,
            iterations=5,
            warmup_iterations=1
        )
        benchmarks["base"] = await self.evaluate_single(base_case, agent)
        
        # TODO: Add more component-specific benchmarks
        # This would require creating agents with different configurations
        
        return benchmarks


# Utility function using Agno's PerfEval
def agno_performance_eval(func: Callable[[], Awaitable[Any]], num_iterations: int = 5) -> Dict[str, Any]:
    """
    Use Agno's built-in performance evaluation.
    
    Args:
        func: Async function to evaluate
        num_iterations: Number of iterations to run
    
    Returns:
        Performance metrics dictionary
    """
    perf_eval = PerfEval(
        func=func,
        num_iterations=num_iterations,
        warmup_runs=1
    )
    
    return perf_eval.run(print_results=True)


# Convenience function for quick performance testing
async def quick_performance_eval(
    test_input: str,
    iterations: int = 5,
    agent_config: Optional[Config] = None
) -> PerformanceMetrics:
    """
    Quick performance evaluation for a single test case.
    
    Args:
        test_input: Input to test
        iterations: Number of iterations
        agent_config: Agent configuration
    
    Returns:
        PerformanceMetrics with detailed results
    """
    evaluator = BlitzPerformanceEval(agent_config=agent_config)
    
    test_case = PerformanceTestCase(
        name="Quick Test",
        input=test_input,
        iterations=iterations,
        warmup_iterations=1
    )
    
    return await evaluator.evaluate_single(test_case) 