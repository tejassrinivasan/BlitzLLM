"""
Reliability evaluation for BlitzAgent focusing on tool call validation.

This module evaluates whether the agent makes expected tool calls,
handles errors gracefully, and maintains consistent behavior.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any, Set
from dataclasses import dataclass
from datetime import datetime
import re

from agno.eval.reliability import ReliabilityEval, ReliabilityResult
from pydantic import BaseModel

from ..agent import BlitzAgent, AgentResponse
from ..config import Config
from ..agent_factory import RuntimeContext, RuntimeMode, ToneStyle


@dataclass
class ToolCallValidation:
    """Results of tool call validation."""
    
    expected_tools: Set[str]
    actual_tools: Set[str]
    missing_tools: Set[str]
    unexpected_tools: Set[str]
    correct_calls: int
    total_expected: int
    validation_passed: bool


@dataclass 
class ErrorHandlingTest:
    """Results of error handling evaluation."""
    
    test_name: str
    error_introduced: str
    agent_handled_gracefully: bool
    response_quality: float  # 0-10 scale
    recovery_time: float
    error_message: Optional[str] = None


@dataclass
class BlitzReliabilityResult:
    """Comprehensive reliability evaluation results."""
    
    # Tool call validation
    tool_validation: ToolCallValidation
    
    # Error handling
    error_handling_tests: List[ErrorHandlingTest]
    error_handling_score: float  # 0-10 scale
    
    # Consistency metrics
    response_consistency: float  # 0-1, measure of similar inputs -> similar outputs
    behavior_stability: float    # 0-1, measure of consistent behavior over time
    
    # Overall reliability
    overall_score: float
    passed: bool
    total_time: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tool_validation": {
                "expected_tools": list(self.tool_validation.expected_tools),
                "actual_tools": list(self.tool_validation.actual_tools),
                "missing_tools": list(self.tool_validation.missing_tools),
                "unexpected_tools": list(self.tool_validation.unexpected_tools),
                "correct_calls": self.tool_validation.correct_calls,
                "total_expected": self.tool_validation.total_expected,
                "validation_passed": self.tool_validation.validation_passed
            },
            "error_handling_tests": [
                {
                    "test_name": test.test_name,
                    "error_introduced": test.error_introduced,
                    "agent_handled_gracefully": test.agent_handled_gracefully,
                    "response_quality": test.response_quality,
                    "recovery_time": test.recovery_time,
                    "error_message": test.error_message
                }
                for test in self.error_handling_tests
            ],
            "error_handling_score": self.error_handling_score,
            "response_consistency": self.response_consistency,
            "behavior_stability": self.behavior_stability,
            "overall_score": self.overall_score,
            "passed": self.passed,
            "total_time": self.total_time,
            "timestamp": datetime.utcnow().isoformat()
        }


class ReliabilityTestCase(BaseModel):
    """Test case for reliability evaluation."""
    
    name: str
    input: str
    expected_tools: List[str]
    expected_response_pattern: Optional[str] = None
    error_scenarios: Optional[List[str]] = None
    consistency_inputs: Optional[List[str]] = None  # Similar inputs for consistency testing
    
    
class BlitzReliabilityEval:
    """
    Reliability evaluation for BlitzAgent.
    
    Tests tool call accuracy, error handling, and behavioral consistency
    to ensure the agent performs reliably across different scenarios.
    """
    
    def __init__(
        self,
        agent_config: Optional[Config] = None,
        agent_context: Optional[RuntimeContext] = None,
        reliability_threshold: float = 0.8,  # 80% reliability required to pass
        consistency_threshold: float = 0.7   # 70% consistency required
    ):
        """Initialize the reliability evaluator."""
        self.agent_config = agent_config or Config()
        self.agent_context = agent_context or RuntimeContext(
            mode=RuntimeMode.INSIGHT,
            tone=ToneStyle.ANALYTICAL
        )
        self.reliability_threshold = reliability_threshold
        self.consistency_threshold = consistency_threshold
    
    async def evaluate_single(
        self,
        test_case: ReliabilityTestCase,
        agent: Optional[BlitzAgent] = None
    ) -> BlitzReliabilityResult:
        """Evaluate reliability for a single test case."""
        start_time = time.time()
        
        # Create agent if not provided
        agent_created = False
        if agent is None:
            agent = BlitzAgent(config=self.agent_config, context=self.agent_context)
            await agent.initialize()
            agent_created = True
        
        try:
            # Run main test
            response = await agent.run(
                message=test_case.input,
                user_id="reliability_test",
                session_id="reliability_test",
                stream=False
            )
            
            # Validate tool calls
            tool_validation = self._validate_tool_calls(response, test_case.expected_tools)
            
            # Test error handling
            error_handling_tests = await self._test_error_handling(
                agent, test_case, test_case.error_scenarios or []
            )
            error_handling_score = self._calculate_error_handling_score(error_handling_tests)
            
            # Test consistency if multiple inputs provided
            consistency_score = await self._test_consistency(
                agent, test_case.consistency_inputs or [test_case.input]
            )
            
            # Test behavioral stability (run same input multiple times)
            stability_score = await self._test_stability(agent, test_case.input)
            
            # Calculate overall reliability score
            overall_score = self._calculate_overall_score(
                tool_validation, error_handling_score, consistency_score, stability_score
            )
            
            total_time = time.time() - start_time
            passed = overall_score >= self.reliability_threshold
            
            return BlitzReliabilityResult(
                tool_validation=tool_validation,
                error_handling_tests=error_handling_tests,
                error_handling_score=error_handling_score,
                response_consistency=consistency_score,
                behavior_stability=stability_score,
                overall_score=overall_score,
                passed=passed,
                total_time=total_time
            )
        
        finally:
            if agent_created and agent:
                await agent.cleanup()
    
    def _validate_tool_calls(
        self,
        response: AgentResponse,
        expected_tools: List[str]
    ) -> ToolCallValidation:
        """Validate that expected tools were called."""
        
        expected_set = set(expected_tools)
        actual_set = set()
        
        # Extract actual tool calls from response
        if hasattr(response, 'tool_calls') and response.tool_calls:
            for tool_call in response.tool_calls:
                if isinstance(tool_call, dict):
                    tool_name = tool_call.get('name', tool_call.get('tool_name', ''))
                    if tool_name:
                        actual_set.add(tool_name)
                elif hasattr(tool_call, 'name'):
                    actual_set.add(tool_call.name)
                elif hasattr(tool_call, 'tool_name'):
                    actual_set.add(tool_call.tool_name)
        
        # Also check response content for tool mentions (backup method)
        if hasattr(response, 'content') and response.content:
            content = response.content.lower()
            for tool in expected_tools:
                if tool.lower() in content or tool.replace('_', ' ').lower() in content:
                    actual_set.add(tool)
        
        missing_tools = expected_set - actual_set
        unexpected_tools = actual_set - expected_set
        correct_calls = len(expected_set.intersection(actual_set))
        
        validation_passed = len(missing_tools) == 0
        
        return ToolCallValidation(
            expected_tools=expected_set,
            actual_tools=actual_set,
            missing_tools=missing_tools, 
            unexpected_tools=unexpected_tools,
            correct_calls=correct_calls,
            total_expected=len(expected_set),
            validation_passed=validation_passed
        )
    
    async def _test_error_handling(
        self,
        agent: BlitzAgent,
        test_case: ReliabilityTestCase,
        error_scenarios: List[str]
    ) -> List[ErrorHandlingTest]:
        """Test how the agent handles various error scenarios."""
        
        error_tests = []
        
        # Default error scenarios if none provided
        if not error_scenarios:
            error_scenarios = [
                "invalid_query",
                "empty_input",
                "network_timeout",
                "database_error"
            ]
        
        for error_scenario in error_scenarios:
            error_test = await self._run_error_scenario(agent, test_case, error_scenario)
            error_tests.append(error_test)
        
        return error_tests
    
    async def _run_error_scenario(
        self,
        agent: BlitzAgent,
        test_case: ReliabilityTestCase,
        error_scenario: str
    ) -> ErrorHandlingTest:
        """Run a specific error scenario test."""
        
        start_time = time.time()
        
        # Create error-inducing input based on scenario
        error_input = self._create_error_input(test_case.input, error_scenario)
        
        try:
            response = await agent.run(
                message=error_input,
                user_id=f"error_test_{error_scenario}",
                session_id=f"error_test_{error_scenario}",
                stream=False
            )
            
            recovery_time = time.time() - start_time
            
            # Evaluate response quality and graceful handling
            handled_gracefully = self._evaluate_error_handling(response, error_scenario)
            response_quality = self._rate_error_response_quality(response)
            
            return ErrorHandlingTest(
                test_name=error_scenario,
                error_introduced=error_input,
                agent_handled_gracefully=handled_gracefully,
                response_quality=response_quality,
                recovery_time=recovery_time
            )
            
        except Exception as e:
            recovery_time = time.time() - start_time
            
            # Agent crashed or threw exception - not graceful
            return ErrorHandlingTest(
                test_name=error_scenario,
                error_introduced=error_input,
                agent_handled_gracefully=False,
                response_quality=0.0,
                recovery_time=recovery_time,
                error_message=str(e)
            )
    
    def _create_error_input(self, original_input: str, error_scenario: str) -> str:
        """Create error-inducing input based on scenario type."""
        
        error_inputs = {
            "invalid_query": "Find me the stats for player 'XYZ123NONEXISTENT' in the year 9999",
            "empty_input": "",
            "network_timeout": original_input + " (Please search extremely obscure historical data that might timeout)",
            "database_error": "SELECT * FROM nonexistent_table WHERE invalid_column = 'test'",
            "malformed_request": "What is the {INVALID_SYNTAX} of @#$%^&*() player???",
            "rate_limit": original_input + " " * 1000,  # Very long input to potentially trigger limits
        }
        
        return error_inputs.get(error_scenario, original_input)
    
    def _evaluate_error_handling(self, response: AgentResponse, error_scenario: str) -> bool:
        """Evaluate if the agent handled the error gracefully."""
        
        if not hasattr(response, 'content') or not response.content:
            return False
        
        content = response.content.lower()
        
        # Look for graceful error handling indicators
        graceful_indicators = [
            "sorry", "unable to", "cannot find", "not available", 
            "error", "issue", "problem", "try again", "invalid",
            "doesn't exist", "not found", "unavailable"
        ]
        
        # Look for helpful alternatives
        helpful_indicators = [
            "instead", "alternatively", "perhaps", "might want to",
            "suggest", "recommend", "try", "available options"
        ]
        
        has_graceful_message = any(indicator in content for indicator in graceful_indicators)
        offers_help = any(indicator in content for indicator in helpful_indicators)
        
        # Good error handling should acknowledge the issue and potentially offer alternatives
        return has_graceful_message and (offers_help or len(content) > 50)
    
    def _rate_error_response_quality(self, response: AgentResponse) -> float:
        """Rate the quality of error response on 0-10 scale."""
        
        if not hasattr(response, 'content') or not response.content:
            return 0.0
        
        content = response.content
        score = 5.0  # Base score
        
        # Positive indicators
        if "sorry" in content.lower() or "apologize" in content.lower():
            score += 1.0  # Polite acknowledgment
        
        if any(word in content.lower() for word in ["instead", "alternatively", "suggest"]):
            score += 2.0  # Offers alternatives
        
        if len(content) > 100:
            score += 1.0  # Detailed response
        
        if "help" in content.lower() or "assist" in content.lower():
            score += 1.0  # Offers help
        
        # Negative indicators  
        if len(content) < 20:
            score -= 2.0  # Too brief
        
        if any(word in content.lower() for word in ["crash", "failed", "exception"]):
            score -= 1.0  # Technical error terms
        
        return max(0.0, min(10.0, score))
    
    async def _test_consistency(self, agent: BlitzAgent, inputs: List[str]) -> float:
        """Test response consistency across similar inputs."""
        
        if len(inputs) < 2:
            return 1.0  # Perfect consistency if only one input
        
        responses = []
        for i, input_text in enumerate(inputs):
            try:
                response = await agent.run(
                    message=input_text,
                    user_id=f"consistency_test_{i}",
                    session_id=f"consistency_test_{i}",
                    stream=False
                )
                responses.append(response.content if hasattr(response, 'content') else str(response))
            except Exception:
                responses.append("")  # Empty response for failed attempts
        
        # Calculate similarity between responses
        return self._calculate_response_similarity(responses)
    
    async def _test_stability(self, agent: BlitzAgent, input_text: str, iterations: int = 3) -> float:
        """Test behavioral stability by running same input multiple times."""
        
        responses = []
        for i in range(iterations):
            try:
                response = await agent.run(
                    message=input_text,
                    user_id=f"stability_test_{i}",
                    session_id=f"stability_test_{i}",
                    stream=False
                )
                responses.append(response.content if hasattr(response, 'content') else str(response))
            except Exception:
                responses.append("")
        
        return self._calculate_response_similarity(responses)
    
    def _calculate_response_similarity(self, responses: List[str]) -> float:
        """Calculate similarity score between responses (0-1 scale)."""
        
        if len(responses) < 2:
            return 1.0
        
        # Simple similarity based on common words and length
        similarities = []
        
        for i in range(len(responses)):
            for j in range(i + 1, len(responses)):
                sim = self._jaccard_similarity(responses[i], responses[j])
                similarities.append(sim)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two text strings."""
        
        if not text1 and not text2:
            return 1.0
        if not text1 or not text2:
            return 0.0
        
        # Convert to word sets
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        intersection = len(words1.intersection(words2))
        union = len(words1.union(words2))
        
        return intersection / union if union > 0 else 0.0
    
    def _calculate_error_handling_score(self, error_tests: List[ErrorHandlingTest]) -> float:
        """Calculate overall error handling score."""
        
        if not error_tests:
            return 10.0  # Perfect score if no errors to handle
        
        graceful_count = sum(1 for test in error_tests if test.agent_handled_gracefully)
        avg_quality = sum(test.response_quality for test in error_tests) / len(error_tests)
        
        # Combine graceful handling rate and average response quality
        graceful_rate = graceful_count / len(error_tests)
        normalized_quality = avg_quality / 10.0
        
        return (graceful_rate * 0.6 + normalized_quality * 0.4) * 10.0
    
    def _calculate_overall_score(
        self,
        tool_validation: ToolCallValidation,
        error_handling_score: float,
        consistency_score: float,
        stability_score: float
    ) -> float:
        """Calculate overall reliability score."""
        
        # Tool call accuracy score (0-1)
        tool_score = tool_validation.correct_calls / max(1, tool_validation.total_expected)
        
        # Normalize error handling score to 0-1
        error_score = error_handling_score / 10.0
        
        # Weighted combination
        weights = {
            'tools': 0.4,      # 40% - Tool calls are critical
            'errors': 0.3,     # 30% - Error handling is important
            'consistency': 0.2, # 20% - Consistency matters
            'stability': 0.1    # 10% - Stability is baseline expectation
        }
        
        overall = (
            tool_score * weights['tools'] +
            error_score * weights['errors'] +
            consistency_score * weights['consistency'] +
            stability_score * weights['stability']
        )
        
        return overall
    
    async def evaluate_batch(
        self,
        test_cases: List[ReliabilityTestCase],
        agent: Optional[BlitzAgent] = None
    ) -> List[BlitzReliabilityResult]:
        """Evaluate multiple reliability test cases."""
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
    
    def create_test_cases(self) -> List[ReliabilityTestCase]:
        """Create default reliability test cases."""
        return [
            ReliabilityTestCase(
                name="Database Query Test",
                input="What was LeBron James' scoring average in 2020?",
                expected_tools=["query_database", "mcp_blitz-agent-python_query"],
                expected_response_pattern=r"\d+\.\d+.*points",
                error_scenarios=["invalid_query", "database_error"],
                consistency_inputs=[
                    "What was LeBron James' scoring average in 2020?",
                    "LeBron James 2020 season scoring average?",
                    "How many points per game did LeBron average in 2020?"
                ]
            ),
            ReliabilityTestCase(
                name="Player Comparison Test",
                input="Compare Steph Curry and Kevin Durant's 2022 season",
                expected_tools=["analyze_player_stats", "query_database"],
                expected_response_pattern=r"(Curry|Durant).*\d+.*points",
                error_scenarios=["invalid_query", "empty_input"],
                consistency_inputs=[
                    "Compare Steph Curry and Kevin Durant's 2022 season",
                    "Curry vs Durant 2022 season comparison",
                    "How did Steph Curry and KD perform in 2022?"
                ]
            ),
            ReliabilityTestCase(
                name="Team Search Test", 
                input="Find recent Lakers games and their results",
                expected_tools=["search_games", "query_database"],
                expected_response_pattern=r"Lakers.*(\d+-\d+|won|lost)",
                error_scenarios=["network_timeout", "invalid_query"],
                consistency_inputs=[
                    "Find recent Lakers games and their results",
                    "Show me Lakers recent game results",
                    "What are the Lakers' latest game outcomes?"
                ]
            ),
            ReliabilityTestCase(
                name="Statistical Analysis Test",
                input="Analyze NBA three-point shooting trends this season",
                expected_tools=["query_database", "analyze_player_stats"],
                expected_response_pattern=r"\d+\.\d+%.*three",
                error_scenarios=["database_error", "malformed_request"],
                consistency_inputs=[
                    "Analyze NBA three-point shooting trends this season",
                    "What are the 3-point shooting trends in NBA this year?",
                    "How has NBA three-point shooting changed this season?"
                ]
            ),
            ReliabilityTestCase(
                name="Error Handling Test",
                input="Find stats for player 'NONEXISTENT_PLAYER_999'",
                expected_tools=["query_database"],
                expected_response_pattern=r"(not found|doesn't exist|unable|sorry)",
                error_scenarios=["invalid_query", "empty_input", "malformed_request"]
            )
        ]


# Convenience function using Agno's ReliabilityEval
async def agno_reliability_eval(
    agent_response,
    expected_tool_calls: List[str],
    print_results: bool = True
) -> Optional[ReliabilityResult]:
    """
    Use Agno's built-in reliability evaluation.
    
    Args:
        agent_response: The agent's response to evaluate
        expected_tool_calls: List of expected tool call names
        print_results: Whether to print results
    
    Returns:
        ReliabilityResult from Agno
    """
    evaluation = ReliabilityEval(
        agent_response=agent_response,
        expected_tool_calls=expected_tool_calls
    )
    
    return evaluation.run(print_results=print_results)


# Convenience function for quick reliability testing
async def quick_reliability_eval(
    test_input: str,
    expected_tools: List[str],
    agent_config: Optional[Config] = None
) -> BlitzReliabilityResult:
    """
    Quick reliability evaluation for a single test case.
    
    Args:
        test_input: Input to test
        expected_tools: List of expected tool names
        agent_config: Agent configuration
    
    Returns:
        BlitzReliabilityResult with detailed reliability metrics
    """
    evaluator = BlitzReliabilityEval(agent_config=agent_config)
    
    test_case = ReliabilityTestCase(
        name="Quick Test",
        input=test_input,
        expected_tools=expected_tools
    )
    
    return await evaluator.evaluate_single(test_case) 