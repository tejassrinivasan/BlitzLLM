import { sportsInsightsAgent, workflowMonitor } from './sports-insights-agent.js';

/**
 * Example usage of the enhanced Sports Insights Agent with streaming and workflow enforcement
 * This works with your Azure OpenAI setup
 */

// Example 1: Basic streaming usage
export async function streamingSportsAnalysis(query: string) {
  console.log(`🏀 Starting sports analysis for: "${query}"`);
  
  try {
    // Initialize workflow monitoring
    workflowMonitor.initSession('streaming-session');
    
    // Use the agent's stream method (this is the correct Mastra API)
    const result = await sportsInsightsAgent.stream(query);

    console.log('🌊 Streaming response...');
    
    // The stream will automatically show the agent's step-by-step thinking and tool usage
    // Mastra handles the streaming of reasoning, tool calls, and results
    
    return result;
    
  } catch (error) {
    console.error('❌ Error during analysis:', error);
    throw error;
  }
}

// Example 2: Monitor workflow compliance
export function checkWorkflowCompliance(sessionId: string = 'streaming-session') {
  const state = workflowMonitor.getWorkflowState(sessionId);
  
  console.log('📋 Workflow State Check:');
  console.log(`- Using Historical DB: ${state?.isUsingHistoricalDB}`);
  console.log(`- Called Get Database Docs: ${state?.hasCalledGetDatabaseDocs}`);
  console.log(`- Called Recall Queries: ${state?.hasCalledRecallQueries}`);
  console.log(`- Last Tool: ${state?.lastToolCalled}`);
  
  return state;
}

// Example 3: Generate text (non-streaming)
export async function generateSportsAnalysis(query: string) {
  console.log(`📊 Generating sports analysis for: "${query}"`);
  
  try {
    workflowMonitor.initSession('generate-session');
    
    // Use generate method for non-streaming response
    const result = await sportsInsightsAgent.generate(query);
    
    console.log('✅ Analysis complete');
    return result;
    
  } catch (error) {
    console.error('❌ Error during generation:', error);
    throw error;
  }
}

// Example usage:
// 
// Streaming (agent will "think out loud" and show tool usage):
// await streamingSportsAnalysis("What was LeBron James' performance in the last Lakers game?");
// 
// Check if workflow was followed correctly:
// checkWorkflowCompliance();
// 
// Non-streaming generation:
// await generateSportsAnalysis("Show me the top 5 NBA scorers from last season");

export const examples = {
  streamingSportsAnalysis,
  checkWorkflowCompliance,
  generateSportsAnalysis
}; 