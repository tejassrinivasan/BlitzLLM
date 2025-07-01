"""
Accuracy evaluation for BlitzAgent using LLM-as-a-judge methodology.

This module evaluates the correctness, completeness, and accuracy of agent responses
against expected outputs using a larger model as the judge.
"""

import asyncio
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime

from agno.models.openai import OpenAIChat
from agno.models.google import Gemini
from agno.models.azure import AzureOpenAI
from agno.eval.accuracy import AccuracyEval, AccuracyResult
from pydantic import BaseModel

from ..agent import BlitzAgent
from ..config import Config
from ..agent_factory import RuntimeContext, RuntimeMode, ToneStyle


@dataclass
class BlitzAccuracyResult:
    """Results from BlitzAgent accuracy evaluation."""
    
    avg_score: float
    scores: List[float]
    evaluations: List[Dict[str, Any]]
    total_time: float
    passed: bool
    threshold: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "avg_score": self.avg_score,
            "scores": self.scores,
            "evaluations": self.evaluations,
            "total_time": self.total_time,
            "passed": self.passed,
            "threshold": self.threshold,
            "timestamp": datetime.utcnow().isoformat()
        }


class SportsDomainTestCase(BaseModel):
    """Test case for sports domain evaluation."""
    
    input: str
    expected_output: str
    additional_guidelines: Optional[str] = None
    expected_tools: Optional[List[str]] = None
    context: Optional[str] = None


class BlitzAccuracyEval:
    """
    Accuracy evaluation for BlitzAgent using LLM-as-a-judge.
    
    Evaluates agent responses against expected outputs using advanced prompting
    and scoring techniques tailored for sports analytics.
    """
    
    def __init__(
        self,
        judge_model: str = "gpt-4o",
        agent_config: Optional[Config] = None,
        agent_context: Optional[RuntimeContext] = None,
        threshold: float = 7.0,
        num_iterations: int = 1
    ):
        """Initialize the accuracy evaluator."""
        self.judge_model = judge_model
        self.agent_config = agent_config or Config()
        self.agent_context = agent_context or RuntimeContext(
            mode=RuntimeMode.INSIGHT,
            tone=ToneStyle.ANALYTICAL
        )
        self.threshold = threshold
        self.num_iterations = num_iterations
        
        # Initialize judge model
        self._judge = self._create_judge_model()
        
        # Sports domain specific guidelines
        self.sports_guidelines = """
        ## SPORTS DOMAIN EVALUATION GUIDELINES
        
        **Data Accuracy (30%):**
        - Statistical accuracy (numbers, percentages, records)
        - Correct player names, team names, dates
        - Accurate game results and scores
        - Proper time periods and seasons
        
        **Analysis Quality (25%):**
        - Insightful interpretation of data
        - Relevant context and comparisons
        - Identification of trends and patterns
        - Understanding of sports concepts
        
        **Completeness (20%):**
        - Addresses all parts of the question
        - Provides sufficient detail for the query type
        - Includes relevant supporting information
        - No major omissions
        
        **Relevance (15%):**
        - Stays focused on the question
        - Provides actionable insights
        - Appropriate level of detail
        - Contextually appropriate
        
        **Clarity & Structure (10%):**
        - Clear, well-organized response
        - Proper use of sports terminology
        - Logical flow of information
        - Professional presentation
        """
    
    def _create_judge_model(self):
        """Create the judge model for evaluation."""
        if "gpt-4" in self.judge_model or "gpt-3.5" in self.judge_model:
            return OpenAIChat(
                id=self.judge_model,
                temperature=0,
                max_tokens=2000
            )
        elif "gemini" in self.judge_model:
            return Gemini(
                id=self.judge_model,
                temperature=0,
                max_tokens=2000
            )
        elif "azure" in self.judge_model:
            return AzureOpenAI(
                id=self.judge_model.replace("azure:", ""),
                temperature=0,
                max_tokens=2000
            )
        else:
            # Default to GPT-4o
            return OpenAIChat(
                id="gpt-4o",
                temperature=0,
                max_tokens=2000
            )
    
    async def evaluate_single(
        self,
        test_case: SportsDomainTestCase,
        agent: Optional[BlitzAgent] = None
    ) -> BlitzAccuracyResult:
        """Evaluate a single test case."""
        start_time = time.time()
        
        # Create agent if not provided
        if agent is None:
            agent = BlitzAgent(config=self.agent_config, context=self.agent_context)
            await agent.initialize()
        
        scores = []
        evaluations = []
        
        try:
            for i in range(self.num_iterations):
                # Get agent response
                agent_response = await agent.run(
                    message=test_case.input,
                    user_id=f"eval_user_{i}",
                    session_id=f"eval_session_{i}",
                    stream=False
                )
                
                # Extract content
                if hasattr(agent_response, 'content'):
                    output = agent_response.content
                elif isinstance(agent_response, dict):
                    output = agent_response.get('content', str(agent_response))
                else:
                    output = str(agent_response)
                
                # Use Agno's AccuracyEval for the actual scoring
                accuracy_eval = AccuracyEval(
                    model=self._judge,
                    input=test_case.input,
                    expected_output=test_case.expected_output,
                    additional_guidelines=self._build_guidelines(test_case),
                    num_iterations=1
                )
                
                # Evaluate with given output
                result = accuracy_eval.run_with_output(
                    output=output,
                    print_results=False
                )
                
                if result:
                    score = result.avg_score
                    scores.append(score)
                    evaluations.append({
                        "iteration": i + 1,
                        "input": test_case.input,
                        "expected": test_case.expected_output,
                        "actual": output,
                        "score": score,
                        "reasoning": getattr(result, 'reasoning', ''),
                        "feedback": getattr(result, 'feedback', '')
                    })
                else:
                    scores.append(0.0)
                    evaluations.append({
                        "iteration": i + 1,
                        "input": test_case.input,
                        "expected": test_case.expected_output,
                        "actual": output,
                        "score": 0.0,
                        "error": "Evaluation failed"
                    })
        
        finally:
            await agent.cleanup()
        
        total_time = time.time() - start_time
        avg_score = sum(scores) / len(scores) if scores else 0.0
        passed = avg_score >= self.threshold
        
        return BlitzAccuracyResult(
            avg_score=avg_score,
            scores=scores,
            evaluations=evaluations,
            total_time=total_time,
            passed=passed,
            threshold=self.threshold
        )
    
    async def evaluate_batch(
        self,
        test_cases: List[SportsDomainTestCase],
        agent: Optional[BlitzAgent] = None
    ) -> List[BlitzAccuracyResult]:
        """Evaluate multiple test cases."""
        results = []
        
        # Create agent once for all evaluations
        if agent is None:
            agent = BlitzAgent(config=self.agent_config, context=self.agent_context)
            await agent.initialize()
        
        try:
            for test_case in test_cases:
                result = await self.evaluate_single(test_case, agent)
                results.append(result)
        finally:
            if agent:
                await agent.cleanup()
        
        return results
    
    def _build_guidelines(self, test_case: SportsDomainTestCase) -> str:
        """Build evaluation guidelines for the test case."""
        guidelines = self.sports_guidelines
        
        if test_case.additional_guidelines:
            guidelines += f"\n\n**Additional Guidelines:**\n{test_case.additional_guidelines}"
        
        if test_case.expected_tools:
            guidelines += f"\n\n**Expected Tool Usage:**\nThe response should demonstrate use of these tools: {', '.join(test_case.expected_tools)}"
        
        if test_case.context:
            guidelines += f"\n\n**Context:**\n{test_case.context}"
        
        return guidelines
    
    def create_test_cases(self) -> List[SportsDomainTestCase]:
        """Create default test cases for sports analytics evaluation."""
        return [
            SportsDomainTestCase(
                input="What was LeBron James' shooting percentage in the 2023 NBA Finals?",
                expected_output="LeBron James shot 49.2% from the field during the 2023 NBA Finals against the Denver Nuggets. He made 61 of 124 field goal attempts across the 5-game series, also shooting 23.5% from three-point range (8/34) and 75.0% from the free-throw line (36/48).",
                additional_guidelines="Should include specific statistical data with proper percentages and context about the series.",
                expected_tools=["query_database", "mcp_blitz-agent-python_query"]
            ),
            SportsDomainTestCase(
                input="Compare Aaron Judge's 2022 season to Babe Ruth's 1927 season",
                expected_output="Aaron Judge's 2022 season (62 HRs, .311 BA, 131 RBIs) broke Babe Ruth's AL record from 1927 (60 HRs, .356 BA, 164 RBIs). While Judge hit more home runs, Ruth had a higher batting average and more RBIs. Both seasons were historic, with Judge playing in a more competitive era with advanced pitching strategies.",
                additional_guidelines="Should provide specific statistical comparisons and historical context.",
                expected_tools=["query_database", "analyze_player_stats"]
            ),
            SportsDomainTestCase(
                input="Which NBA team has the best three-point shooting this season?",
                expected_output="The Boston Celtics lead the NBA in three-point shooting percentage at 38.2% this season, making 16.8 three-pointers per game on 43.9 attempts. They're followed by the Denver Nuggets (37.1%) and Miami Heat (36.8%). The Celtics' exceptional shooting is driven by players like Jayson Tatum and Jaylen Brown.",
                additional_guidelines="Should include current season statistics with team names, percentages, and key players.",
                expected_tools=["query_database", "search_games"]
            ),
            SportsDomainTestCase(
                input="Analyze the correlation between MLB team payroll and playoff success",
                expected_output="There's a moderate positive correlation (r≈0.35) between MLB team payroll and playoff success over the past decade. High-payroll teams like the Dodgers and Yankees make playoffs more consistently, but mid-market teams like the Rays and Guardians show that smart roster construction can overcome payroll disadvantages. The correlation is stronger for regular season wins than playoff advancement.",
                additional_guidelines="Should include statistical analysis, specific examples, and nuanced interpretation.",
                expected_tools=["query_database", "analyze_player_stats"]
            ),
            SportsDomainTestCase(
                input="Who are the top 5 rookies in the NBA this season?",
                expected_output="The top 5 NBA rookies this season based on performance are: 1) Victor Wembanyama (SAS) - 21.2 PPG, 10.8 REB, 3.2 BLK; 2) Chet Holmgren (OKC) - 16.8 PPG, 7.9 REB; 3) Brandon Miller (CHA) - 15.6 PPG, 4.2 REB; 4) Ausar Thompson (DET) - 8.9 PPG, 6.8 REB, 1.9 STL; 5) Dereck Lively II (DAL) - 9.1 PPG, 7.8 REB. Wembanyama is the clear frontrunner for Rookie of the Year.",
                additional_guidelines="Should include current statistics, team abbreviations, and ranking rationale.",
                expected_tools=["query_database", "analyze_player_stats"]
            )
        ]


# Convenience function for quick evaluation
async def quick_accuracy_eval(
    test_input: str,
    expected_output: str,
    additional_guidelines: Optional[str] = None,
    judge_model: str = "gpt-4o",
    threshold: float = 7.0
) -> BlitzAccuracyResult:
    """
    Quick accuracy evaluation for a single test case.
    
    Args:
        test_input: The input question/prompt
        expected_output: Expected response from the agent
        additional_guidelines: Additional evaluation guidelines
        judge_model: Model to use as judge
        threshold: Minimum score to pass
    
    Returns:
        BlitzAccuracyResult with evaluation details
    """
    evaluator = BlitzAccuracyEval(
        judge_model=judge_model,
        threshold=threshold,
        num_iterations=1
    )
    
    test_case = SportsDomainTestCase(
        input=test_input,
        expected_output=expected_output,
        additional_guidelines=additional_guidelines
    )
    
    return await evaluator.evaluate_single(test_case) 