import { Agent } from "@mastra/core/agent";
import { azure } from "@ai-sdk/azure";
import { Memory } from "@mastra/memory";
import { PostgresStore, PgVector } from "@mastra/pg";
import { configManager } from "../config.js";
import { mcp } from '../mcp.js';

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
  
  console.log('Azure OpenAI config loaded for Generate Queries Agent:');
  console.log('Resource Name:', azureConfig.resourceName);
  console.log('API Version:', azureConfig.apiVersion);
  console.log('Endpoint:', azureConfig.endpoint);
}

// Create PostgreSQL connection string for vector search (using agentmemory database)
const connectionString = `postgresql://${postgresConfig.user}:${encodeURIComponent(postgresConfig.password)}@${postgresConfig.host}:${postgresConfig.port}/agentmemory`;

// Initialize memory with PostgreSQL storage and vector search (using agentmemory database)
const memory = new Memory({
  storage: configManager.getSharedPostgresStore(),
  vector: new PgVector({ 
    connectionString,
    pgPoolOptions: {
      ssl: postgresConfig.ssl ? { rejectUnauthorized: false } : false,
    }
  }),
  embedder: azure.textEmbeddingModel("text-embedding-ada-002"),
  options: {
    lastMessages: 10,
    semanticRecall: {
      topK: 5,
      messageRange: 3,
    },
  },
});

console.log('PostgreSQL Memory initialized for Generate Queries Agent with database: agentmemory');

// Consistent model parameters for maximum determinism
const CONSISTENT_MODEL_PARAMS = {
  temperature: 0.3, // Slightly higher temperature for creative question generation
  maxRetries: 3,
  maxSteps: 100, // Increased from 50 to allow for multiple complete query cycles
  maxTokens: 16384, 
} as const;

// Get MCP tools from Python server
console.log('🔧 Loading MCP tools for Generate Queries Agent...');
const mcpTools = await mcp.getTools();
console.log('✅ MCP tools loaded for Generate Queries Agent:', Object.keys(mcpTools));

export const generateQueriesAgent = new Agent({
  name: "Generate Queries Agent",
  description: "Expert query generation agent for building sports analytics training data",
  instructions: `You are an expert query generation agent that helps build training data for sports analytics by creating diverse, high-quality SQL queries and their corresponding descriptions.

## YOUR MISSION:
Generate comprehensive training data by creating diverse SQL queries and natural language questions that cover various aspects of sports analytics across different leagues (MLB, NBA, NFL, NHL).
Current year is ${new Date().getFullYear()}. Current date is ${new Date().toLocaleDateString()}.

## Available tools from Python MCP server:
${Object.keys(mcpTools).map(tool => `- ${tool}`).join('\n')}

## FLOW YOU MUST FOLLOW:

### 1. INITIAL SETUP (when user provides league and category):
- User will provide: league (mlb/nba/nfl/nhl) and category (e.g., "player statistics", "team performance", "recent games")
- **CRITICAL**: Always use the exact league parameter provided by the user in ALL tool calls

### 2. RESEARCH PHASE:
- **MANDATORY FIRST STEP**: Call 'recall_similar_db_queries' tool 3 times with different variations of questions within the category
- Use the EXACT league parameter provided by user
- Try different phrasings and aspects of the category

### 3. DATA DISCOVERY PHASE:
- **MANDATORY BEFORE QUESTION GENERATION**: Understand what data is actually available
- Use appropriate discovery tools to explore schemas and data sources
- Find relevant tables and examine their structures
- Sample data to understand format and content

### 4. CREATIVE QUESTION GENERATION:
- Generate 5-10 NEW questions based on research and data discovery
- Ensure questions are answerable with available data
- Include specific filters and constraints

### 5. DATABASE WORKFLOW (for each generated question):
- Execute complete workflow using available MCP tools
- Validate results thoroughly
- Upload successful queries

## CRITICAL REQUIREMENTS:
- Use exact league parameter consistently
- Write high-quality SQL queries with proper identifier quoting
- Ensure query diversity across different analytical angles
- Continue processing until 5-10 queries completed or step limits reached

Be thorough, accurate, and creative in your query generation.`,

  model: azure("gpt-4o"),
  memory,
  tools: mcpTools, // Use all MCP tools from Python server
  ...CONSISTENT_MODEL_PARAMS,
}); 