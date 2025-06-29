import { Agent } from "@mastra/core/agent";
import { azure } from "@ai-sdk/azure";
import { Memory } from "@mastra/memory";
import { PostgresStore, PgVector } from "@mastra/pg";
import { configManager } from "../config.js";
import { fileURLToPath } from 'url';
import { dirname } from 'path';
import { mcp } from '../mcp.js';
import { z } from 'zod';
import { StepResult, StepSuccess } from "@mastra/core/workflows";
import { ToolCallFilter, TokenLimiter } from "@mastra/memory/processors";

// ES module compatible __dirname equivalent
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Define the structured output schema for the agent response
export const sportsAnalysisSchema = z.object({
  analysis: z.string().describe("Your 1-2 sentence, powerful response to the user's question (use markdown for formatting if response is long)"),
  explanation: z.string().describe("Brief explanation of your analysis methodology and data sources used"),
  links: z.array(z.object({
    type: z.enum(["player", "team", "matchup", "source"]).describe("Type of entity or source"),
    name: z.string().describe("Entity name (for matchups: Away Team @ Home Team, for sources: Website/API name)")
  })).describe("Array of relevant links and sources")
});

// Get PostgreSQL config for memory storage
const postgresConfig = configManager.getServiceConfig('postgres');

// Get Azure OpenAI config
const azureConfig = configManager.getServiceConfig('azure.openai');

// Set Azure environment variables for the AI SDK
if (azureConfig && azureConfig.enabled) {
  process.env.AZURE_API_KEY = azureConfig.apiKey;
  process.env.AZURE_RESOURCE_NAME = azureConfig.resourceName;
  process.env.AZURE_OPENAI_ENDPOINT = azureConfig.endpoint;
  process.env.AZURE_OPENAI_API_VERSION = azureConfig.apiVersion;
  
  console.log('Azure OpenAI config loaded:');
  console.log('Resource Name:', azureConfig.resourceName);
  console.log('API Version:', azureConfig.apiVersion);
  console.log('Endpoint:', azureConfig.endpoint);
} else {
  throw new Error('Azure OpenAI configuration is required. Please configure azure.openai in your config.');
}

// Create PostgreSQL connection string for vector search (using agentmemory database)
const connectionString = `postgresql://${postgresConfig.user}:${encodeURIComponent(postgresConfig.password)}@${postgresConfig.host}:${postgresConfig.port}/agentmemory`;

// Configure Azure OpenAI model
console.log('🤖 Using Azure OpenAI model: gpt-4o');
const model = azure("gpt-4o");
const embedder = azure.textEmbeddingModel("text-embedding-ada-002");

// Initialize memory with PostgreSQL storage and vector search (using agentmemory database)
const memory = new Memory({
  storage: configManager.getSharedPostgresStore(),
  processors: [
    new TokenLimiter(127000),
    new ToolCallFilter({
      exclude: ["blitzAgent_validate", "blitzAgent_upload"]
    })
  ],
  vector: new PgVector({ 
    connectionString,
    pgPoolOptions: {
      ssl: postgresConfig.ssl ? { rejectUnauthorized: false } : false,
    }
  }),
  embedder: embedder,
  options: {
    lastMessages: 10,
    semanticRecall: {
      topK: 3,
      messageRange: 2,
    },
  },
});

console.log('PostgreSQL Memory initialized with database: agentmemory');

// Add memory debugging
console.log('🧠 Memory Configuration:');
console.log('- Storage: PostgresStore with database "agentmemory"');
console.log('- Vector: PgVector with SSL configuration');
console.log('- Embedder: Azure text-embedding-ada-002');
console.log('- Model: Azure OpenAI gpt-4o');
console.log('- LastMessages: 10');
console.log('- SemanticRecall: enabled with topK=3, messageRange=2');

// Get MCP tools from Python server
console.log('🔧 Loading MCP tools from Python server...');
const mcpTools = await mcp.getTools();
console.log('✅ MCP tools loaded:', Object.keys(mcpTools));

// Debug: Log the first few tools to see their schemas
console.log('🔍 Tool Schemas Debug:');
Object.entries(mcpTools).slice(0, 3).forEach(([toolName, tool]) => {
  console.log(`Tool: ${toolName}`);
  console.log(`Description: ${tool.description}`);
  console.log(`Schema:`, JSON.stringify(tool.schema, null, 2));
  console.log('---');
});

// Enhanced workflow state tracking
class WorkflowStateTracker {
  private state = new Map<string, {
    hasCalledGetDatabaseDocs: boolean;
    hasCalledRecallQueries: boolean;
    isUsingHistoricalDB: boolean;
    lastToolCalled: string | null;
  }>();

  initSession(sessionId: string) {
    this.state.set(sessionId, {
      hasCalledGetDatabaseDocs: false,
      hasCalledRecallQueries: false,
      isUsingHistoricalDB: false,
      lastToolCalled: null
    });
  }

  updateToolCall(sessionId: string, toolName: string) {
    const session = this.state.get(sessionId);
    if (!session) return;

    session.lastToolCalled = toolName;

    if (toolName === 'blitzAgent_get_database_documentation') {
      session.hasCalledGetDatabaseDocs = true;
      session.isUsingHistoricalDB = true;
    } else if (toolName === 'blitzAgent_recall_similar_db_queries') {
      session.hasCalledRecallQueries = true;
    }

    this.state.set(sessionId, session);
  }

  shouldEnforceRecallQueries(sessionId: string): boolean {
    const session = this.state.get(sessionId);
    return session?.isUsingHistoricalDB && session?.hasCalledGetDatabaseDocs && !session?.hasCalledRecallQueries || false;
  }

  getSessionState(sessionId: string) {
    return this.state.get(sessionId) || null;
  }
}

const workflowTracker = new WorkflowStateTracker();

export const sportsInsightsAgent = new Agent({
  name: "Sports Insights Agent",
  description: "Advanced sports analytics agent specializing in MLB and NBA data analysis with streaming capabilities",
  instructions: `
  You are an AI sports analytics agent with deep expertise in MLB and NBA data.

  Today's date: ${new Date().toLocaleDateString()}  
  Current time: ${new Date().toLocaleTimeString()}  
  Current year: ${new Date().getFullYear()}

  ---
  ## STREAMING AND TRANSPARENCY
  
  COMMUNICATE YOUR PROCESS: As you work through analysis:
  - Announce which data source you're consulting and why
  - Explain what you're looking for before calling tools
  - Share preliminary findings as you gather data
  - Describe how you're connecting different pieces of information
  - Think step-by-step through complex problems out loud

  ---
  ## DATA SOURCES AVAILABLE

  You have access to three distinct sources:

  ### 1. HISTORICAL DATABASE (PostgreSQL) - Only contains data until yesterday

  CRITICAL WORKFLOW ENFORCEMENT (EVERY TIME YOU USE HISTORICAL DB):
  
  **MANDATORY SEQUENCE - NO EXCEPTIONS:**
  1. **FIRST:** blitzAgent_get_database_documentation (to understand schema)
  2. **SECOND:** blitzAgent_recall_similar_db_queries (to check for existing similar queries)
  3. **THEN:** If recall provides sufficient info → blitzAgent_query directly
  4. **OTHERWISE:** blitzAgent_search_tables → blitzAgent_inspect → blitzAgent_sample → blitzAgent_query
  5. **ALWAYS:** blitzAgent_validate (immediate validation required)
  6. **IF VALIDATION PASSES:** blitzAgent_upload (store the query for future recall)

  **CRITICAL ENFORCEMENT RULES:**
  - If you call blitzAgent_get_database_documentation, you MUST call blitzAgent_recall_similar_db_queries next
  - NEVER skip blitzAgent_recall_similar_db_queries when using the historical database
  - blitzAgent_validate is MANDATORY after every blitzAgent_query
  - If validation suggests improvements, iterate the process automatically
  - Continue the full workflow until completion - no premature stopping

  ---
  ### 2. API ENDPOINTS (Live/Upcoming Games, Odds, Predictions)
  - Use for real-time betting lines, starting lineups, scheduled games, projections
  - Always explain which API endpoint you're calling and why

  ---
  ### 3. WEB SCRAPING & SEARCH - Enhanced with streaming commentary
  - Always announce your search strategy and targets
  - Cite source URLs and explain relevance
  - Stream findings as you discover them
  - Use to supplement other data sources generously

  ---
  ## ENHANCED RESPONSE STANDARDS
  
  **Process Transparency:**
  - Stream your reasoning and tool usage in real-time
  - Explain your analytical approach before executing
  - Share intermediate findings and how they connect
  
  **Final Analysis:**
  - 1-2 sentence powerful conclusion with specific data points
  - Brief methodology explanation with data sources cited
  - Specific URLs for web-scraped content
  - Never reference internal tool names or database specifics to users
  
  **Quality Assurance:**
  - Handle edge cases gracefully with explanation
  - State confidence levels and limitations
  - Provide context for data recency and relevance
  `,
  model: model,
  tools: mcpTools,
  memory,
  defaultStreamOptions: {
    maxRetries: 3,
    maxSteps: 25, // Increased for enhanced workflow
    temperature: 0.1, // Slightly higher for more natural thinking-out-loud
    maxTokens: 16384,
    // output: sportsAnalysisSchema, // Re-enable when ready
  },
});

// Workflow monitoring utility
export const workflowMonitor = {
  trackToolCall: (toolName: string, sessionId: string = 'default') => {
    workflowTracker.updateToolCall(sessionId, toolName);
    console.log(`🔧 Tool called: ${toolName}`);
    
    if (workflowTracker.shouldEnforceRecallQueries(sessionId)) {
      console.log('⚠️ WORKFLOW REMINDER: Should call blitzAgent_recall_similar_db_queries after blitzAgent_get_database_documentation');
    }
  },
  
  getWorkflowState: (sessionId: string = 'default') => {
    return workflowTracker.getSessionState(sessionId);
  },
  
  initSession: (sessionId: string = 'default') => {
    workflowTracker.initSession(sessionId);
    console.log(`🚀 Workflow session initialized: ${sessionId}`);
  }
}; 