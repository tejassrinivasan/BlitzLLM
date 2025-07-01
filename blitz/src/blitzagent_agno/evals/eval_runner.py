"""
Evaluation runner for orchestrating BlitzAgent evaluations.

This module provides a unified interface to run accuracy, performance, 
and reliability evaluations together or separately.
"""

import asyncio
import time
import json
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from ..agent import BlitzAgent
from ..config import Config
from ..agent_factory import RuntimeContext, RuntimeMode, ToneStyle
from .accuracy_eval import BlitzAccuracyEval, SportsDomainTestCase, BlitzAccuracyResult
from .performance_eval import BlitzPerformanceEval, PerformanceTestCase, PerformanceMetrics
from .reliability_eval import BlitzReliabilityEval, ReliabilityTestCase, BlitzReliabilityResult


@dataclass
class EvalSummary:
    """Summary of all evaluation results."""
    
    accuracy_results: List[BlitzAccuracyResult]
    performance_results: List[PerformanceMetrics]
    reliability_results: List[BlitzReliabilityResult]
    
    # Summary statistics
    avg_accuracy_score: float
    avg_performance_latency: float
    avg_reliability_score: float
    
    # Overall assessment
    overall_passed: bool
    total_evaluation_time: float
    
    # Metadata
    timestamp: str
    agent_config: Dict[str, Any]


class EvalConfig(BaseModel):
    """Configuration for evaluation runs."""
    
    # Which evaluations to run
    run_accuracy: bool = True
    run_performance: bool = True
    run_reliability: bool = True
    
    # Evaluation parameters
    accuracy_threshold: float = 7.0
    performance_max_latency: float = 10.0  # seconds
    reliability_threshold: float = 0.8
    
    # Test parameters
    num_iterations: int = 3
    warmup_iterations: int = 1


class EvalSuite:
    """Complete evaluation suite for BlitzAgent."""
    
    def __init__(
        self,
        agent_config: Optional[Config] = None,
        eval_config: Optional[EvalConfig] = None
    ):
        """Initialize the evaluation suite."""
        self.agent_config = agent_config or Config()
        self.eval_config = eval_config or EvalConfig()
        
        # Initialize evaluators
        self.accuracy_eval = BlitzAccuracyEval(
            agent_config=self.agent_config,
            threshold=self.eval_config.accuracy_threshold
        ) if self.eval_config.run_accuracy else None
        
        self.performance_eval = BlitzPerformanceEval(
            agent_config=self.agent_config
        ) if self.eval_config.run_performance else None
        
        self.reliability_eval = BlitzReliabilityEval(
            agent_config=self.agent_config,
            reliability_threshold=self.eval_config.reliability_threshold
        ) if self.eval_config.run_reliability else None
    
    async def run_full_evaluation(
        self,
        agent: Optional[BlitzAgent] = None
    ) -> EvalSummary:
        """Run the complete evaluation suite."""
        
        start_time = time.time()
        
        # Create agent once for all evaluations
        agent_created = False
        if agent is None:
            context = RuntimeContext(mode=RuntimeMode.INSIGHT, tone=ToneStyle.ANALYTICAL)
            agent = BlitzAgent(config=self.agent_config, context=context)
            await agent.initialize()
            agent_created = True
        
        try:
            # Run all evaluations
            accuracy_results = await self._run_accuracy_evaluation(agent)
            performance_results = await self._run_performance_evaluation(agent)
            reliability_results = await self._run_reliability_evaluation(agent)
            
            # Calculate summary statistics
            summary = self._calculate_summary(
                accuracy_results, performance_results, reliability_results,
                time.time() - start_time
            )
            
            return summary
        
        finally:
            if agent_created and agent:
                await agent.cleanup()
    
    async def _run_accuracy_evaluation(self, agent: BlitzAgent) -> List[BlitzAccuracyResult]:
        """Run accuracy evaluations."""
        if not self.accuracy_eval:
            return []
        
        test_cases = self.accuracy_eval.create_test_cases()
        print(f"🎯 Running accuracy evaluation with {len(test_cases)} test cases...")
        
        results = []
        for i, test_case in enumerate(test_cases):
            print(f"  Running accuracy test {i+1}/{len(test_cases)}")
            result = await self.accuracy_eval.evaluate_single(test_case, agent)
            results.append(result)
        
        return results
    
    async def _run_performance_evaluation(self, agent: BlitzAgent) -> List[PerformanceMetrics]:
        """Run performance evaluations."""
        if not self.performance_eval:
            return []
        
        test_cases = self.performance_eval.create_test_cases()
        print(f"⚡ Running performance evaluation with {len(test_cases)} test cases...")
        
        results = []
        for i, test_case in enumerate(test_cases):
            print(f"  Running performance test {i+1}/{len(test_cases)}: {test_case.name}")
            result = await self.performance_eval.evaluate_single(test_case, agent)
            results.append(result)
        
        return results
    
    async def _run_reliability_evaluation(self, agent: BlitzAgent) -> List[BlitzReliabilityResult]:
        """Run reliability evaluations."""
        if not self.reliability_eval:
            return []
        
        test_cases = self.reliability_eval.create_test_cases()
        print(f"🔧 Running reliability evaluation with {len(test_cases)} test cases...")
        
        results = []
        for i, test_case in enumerate(test_cases):
            print(f"  Running reliability test {i+1}/{len(test_cases)}: {test_case.name}")
            result = await self.reliability_eval.evaluate_single(test_case, agent)
            results.append(result)
        
        return results
    
    def _calculate_summary(
        self,
        accuracy_results: List[BlitzAccuracyResult],
        performance_results: List[PerformanceMetrics],
        reliability_results: List[BlitzReliabilityResult],
        total_time: float
    ) -> EvalSummary:
        """Calculate summary statistics from all evaluation results."""
        
        # Calculate averages
        avg_accuracy = sum(r.avg_score for r in accuracy_results) / max(1, len(accuracy_results))
        avg_latency = sum(r.avg_latency for r in performance_results) / max(1, len(performance_results))
        avg_reliability = sum(r.overall_score for r in reliability_results) / max(1, len(reliability_results))
        
        # Determine overall pass/fail
        accuracy_passed = all(r.passed for r in accuracy_results) if accuracy_results else True
        performance_passed = all(
            r.avg_latency <= self.eval_config.performance_max_latency 
            for r in performance_results
        ) if performance_results else True
        reliability_passed = all(r.passed for r in reliability_results) if reliability_results else True
        
        overall_passed = accuracy_passed and performance_passed and reliability_passed
        
        return EvalSummary(
            accuracy_results=accuracy_results,
            performance_results=performance_results,
            reliability_results=reliability_results,
            avg_accuracy_score=avg_accuracy,
            avg_performance_latency=avg_latency,
            avg_reliability_score=avg_reliability,
            overall_passed=overall_passed,
            total_evaluation_time=total_time,
            timestamp=datetime.utcnow().isoformat(),
            agent_config=self.agent_config.to_dict()
        )


class EvalRunner:
    """Simple evaluation runner for individual eval types."""
    
    @staticmethod
    async def run_accuracy_eval(
        test_cases: Optional[List[SportsDomainTestCase]] = None,
        agent_config: Optional[Config] = None,
        judge_model: str = "gpt-4o",
        threshold: float = 7.0
    ) -> List[BlitzAccuracyResult]:
        """Run only accuracy evaluation."""
        
        evaluator = BlitzAccuracyEval(
            judge_model=judge_model,
            agent_config=agent_config,
            threshold=threshold
        )
        
        if test_cases is None:
            test_cases = evaluator.create_test_cases()
        
        return await evaluator.evaluate_batch(test_cases)


# Convenience function for quick evaluation
async def quick_eval(
    test_input: str,
    expected_output: Optional[str] = None,
    expected_tools: Optional[List[str]] = None,
    agent_config: Optional[Config] = None
) -> Dict[str, Any]:
    """Quick evaluation of a single input across all dimensions."""
    
    results = {}
    
    # Accuracy evaluation (if expected output provided)
    if expected_output:
        from .accuracy_eval import quick_accuracy_eval
        accuracy_result = await quick_accuracy_eval(
            test_input, expected_output, agent_config=agent_config
        )
        results['accuracy'] = accuracy_result.to_dict()
    
    # Performance evaluation
    from .performance_eval import quick_performance_eval
    performance_result = await quick_performance_eval(
        test_input, agent_config=agent_config
    )
    results['performance'] = performance_result.to_dict()
    
    # Reliability evaluation (if expected tools provided)
    if expected_tools:
        from .reliability_eval import quick_reliability_eval
        reliability_result = await quick_reliability_eval(
            test_input, expected_tools, agent_config=agent_config
        )
        results['reliability'] = reliability_result.to_dict()
    
    return results
