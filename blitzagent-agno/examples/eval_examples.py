"""
Example scripts demonstrating how to use BlitzAgent evaluation system.

This module shows various ways to evaluate your BlitzAgent across
accuracy, performance, and reliability dimensions.
"""

import asyncio
from blitzagent_agno.evals import (
    BlitzAccuracyEval, 
    BlitzPerformanceEval, 
    BlitzReliabilityEval,
    EvalSuite,
    EvalConfig,
    quick_eval
)
from blitzagent_agno.evals.accuracy_eval import SportsDomainTestCase
from blitzagent_agno.evals.performance_eval import PerformanceTestCase
from blitzagent_agno.evals.reliability_eval import ReliabilityTestCase
from blitzagent_agno.config import Config
from blitzagent_agno.agent_factory import RuntimeContext, RuntimeMode, ToneStyle


async def example_accuracy_evaluation():
    """Example: Run accuracy evaluation with custom test cases."""
    
    print("🎯 Running Accuracy Evaluation Example")
    print("="*50)
    
    # Create custom test cases
    test_cases = [
        SportsDomainTestCase(
            input="Who won the 2023 NBA Finals?",
            expected_output="The Denver Nuggets won the 2023 NBA Finals, defeating the Miami Heat 4-1 in the series. This was the Nuggets' first NBA championship in franchise history.",
            additional_guidelines="Should include the series score and mention it was Denver's first championship."
        ),
        SportsDomainTestCase(
            input="What was Stephen Curry's three-point percentage in 2022?",
            expected_output="Stephen Curry shot 42.7% from three-point range during the 2021-22 NBA season, making 285 three-pointers on 668 attempts.",
            additional_guidelines="Should include specific percentage and attempt numbers."
        )
    ]
    
    # Run evaluation
    evaluator = BlitzAccuracyEval(
        judge_model="gpt-4o",
        threshold=7.0
    )
    
    results = await evaluator.evaluate_batch(test_cases)
    
    # Print results
    for i, result in enumerate(results):
        print(f"\nTest {i+1}:")
        print(f"  Average Score: {result.avg_score:.1f}/10")
        print(f"  Passed: {'✅' if result.passed else '❌'}")
        print(f"  Total Time: {result.total_time:.2f}s")


async def example_performance_evaluation():
    """Example: Run performance evaluation with custom test cases."""
    
    print("\n⚡ Running Performance Evaluation Example")
    print("="*50)
    
    # Create custom test cases
    test_cases = [
        PerformanceTestCase(
            name="Quick Stats Query",
            input="What is LeBron's career scoring average?",
            iterations=5,
            warmup_iterations=1,
            expected_max_latency=3.0
        ),
        PerformanceTestCase(
            name="Complex Analysis",
            input="Compare the top 5 NBA teams' offensive efficiency this season",
            iterations=3,
            warmup_iterations=1,
            expected_max_latency=10.0
        )
    ]
    
    # Run evaluation
    evaluator = BlitzPerformanceEval()
    results = await evaluator.evaluate_batch(test_cases)
    
    # Print results
    for i, result in enumerate(results):
        print(f"\nTest {i+1} ({test_cases[i].name}):")
        print(f"  Average Latency: {result.avg_latency:.2f}s")
        print(f"  P95 Latency: {result.p95_latency:.2f}s")
        print(f"  Success Rate: {result.success_rate:.1%}")
        print(f"  Operations/sec: {result.operations_per_second:.2f}")


async def example_reliability_evaluation():
    """Example: Run reliability evaluation with custom test cases."""
    
    print("\n🔧 Running Reliability Evaluation Example")
    print("="*50)
    
    # Create custom test cases
    test_cases = [
        ReliabilityTestCase(
            name="Database Query Reliability",
            input="Find LeBron James' stats for the 2020 season",
            expected_tools=["query_database", "mcp_blitz-agent-python_query"],
            error_scenarios=["invalid_query", "database_error"],
            consistency_inputs=[
                "Find LeBron James' stats for the 2020 season",
                "LeBron James 2020 season statistics",
                "What were LeBron's numbers in 2020?"
            ]
        ),
        ReliabilityTestCase(
            name="Error Handling Test",
            input="Find stats for nonexistent player FAKE_PLAYER_123",
            expected_tools=["query_database"],
            error_scenarios=["invalid_query", "empty_input"]
        )
    ]
    
    # Run evaluation
    evaluator = BlitzReliabilityEval(reliability_threshold=0.8)
    results = await evaluator.evaluate_batch(test_cases)
    
    # Print results
    for i, result in enumerate(results):
        print(f"\nTest {i+1} ({test_cases[i].name}):")
        print(f"  Overall Score: {result.overall_score:.2f}")
        print(f"  Passed: {'✅' if result.passed else '❌'}")
        print(f"  Tool Validation: {'✅' if result.tool_validation.validation_passed else '❌'}")
        print(f"  Error Handling Score: {result.error_handling_score:.1f}/10")
        print(f"  Consistency: {result.response_consistency:.2f}")


async def example_full_evaluation_suite():
    """Example: Run the complete evaluation suite."""
    
    print("\n🚀 Running Full Evaluation Suite Example")
    print("="*50)
    
    # Configure evaluation
    eval_config = EvalConfig(
        run_accuracy=True,
        run_performance=True,
        run_reliability=True,
        accuracy_threshold=7.0,
        performance_max_latency=8.0,
        reliability_threshold=0.8,
        num_iterations=3
    )
    
    # Create and run evaluation suite
    suite = EvalSuite(eval_config=eval_config)
    summary = await suite.run_full_evaluation()
    
    # Print summary
    print(f"\n📊 EVALUATION SUMMARY")
    print(f"Overall Status: {'✅ PASSED' if summary.overall_passed else '❌ FAILED'}")
    print(f"Total Time: {summary.total_evaluation_time:.2f}s")
    print(f"")
    print(f"Accuracy: {summary.avg_accuracy_score:.1f}/10")
    print(f"Performance: {summary.avg_performance_latency:.2f}s avg latency")
    print(f"Reliability: {summary.avg_reliability_score:.2f}")


async def example_quick_evaluation():
    """Example: Quick evaluation of a single input."""
    
    print("\n⚡ Running Quick Evaluation Example")
    print("="*50)
    
    # Quick evaluation with all dimensions
    results = await quick_eval(
        test_input="Who is the NBA's all-time leading scorer?",
        expected_output="LeBron James is the NBA's all-time leading scorer with over 38,000 career points, surpassing Kareem Abdul-Jabbar's previous record of 38,387 points.",
        expected_tools=["query_database", "mcp_blitz-agent-python_query"]
    )
    
    print(f"Quick Evaluation Results:")
    if 'accuracy' in results:
        print(f"  Accuracy Score: {results['accuracy']['avg_score']:.1f}/10")
    if 'performance' in results:
        print(f"  Performance: {results['performance']['avg_latency']:.2f}s")
    if 'reliability' in results:
        print(f"  Reliability: {results['reliability']['overall_score']:.2f}")


async def example_custom_agent_evaluation():
    """Example: Evaluate with custom agent configuration."""
    
    print("\n🎯 Running Custom Agent Evaluation Example")
    print("="*50)
    
    # Create custom agent configuration
    config = Config()
    context = RuntimeContext(
        mode=RuntimeMode.CONVERSATION,
        tone=ToneStyle.CASUAL
    )
    
    # Run accuracy evaluation with custom configuration
    evaluator = BlitzAccuracyEval(
        agent_config=config,
        agent_context=context,
        judge_model="gpt-4o",
        threshold=6.0  # Lower threshold for casual tone
    )
    
    test_case = SportsDomainTestCase(
        input="Tell me about Michael Jordan",
        expected_output="Michael Jordan is widely considered the greatest basketball player of all time. He won 6 NBA championships with the Chicago Bulls, earned 5 MVP awards, and was known for his incredible scoring ability and clutch performances.",
        additional_guidelines="Response should be casual and conversational while being informative."
    )
    
    result = await evaluator.evaluate_single(test_case)
    
    print(f"Custom Agent Evaluation:")
    print(f"  Score: {result.avg_score:.1f}/10")
    print(f"  Passed: {'✅' if result.passed else '❌'}")


async def run_all_examples():
    """Run all evaluation examples."""
    
    print("🚀 BlitzAgent Evaluation Examples")
    print("="*80)
    
    try:
        await example_accuracy_evaluation()
        await example_performance_evaluation() 
        await example_reliability_evaluation()
        await example_full_evaluation_suite()
        await example_quick_evaluation()
        await example_custom_agent_evaluation()
        
        print("\n✅ All examples completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Error running examples: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_examples()) 