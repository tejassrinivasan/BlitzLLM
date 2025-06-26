import { readFileSync } from 'fs';
import path, { dirname, join } from 'path';
import { fileURLToPath } from 'url';
import { PostgresStore } from '@mastra/pg';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export interface Config {
  services: {
    firecrawl: {
      enabled: boolean;
      apiKey: string;
      description: string;
    };
    sportsdata: {
      enabled: boolean;
      apiKey: string;
      description: string;
    };
    azure: {
      search: {
        enabled: boolean;
        endpoint: string;
        apiKey: string;
        indexName: string;
        description: string;
      };
      openai: {
        enabled: boolean;
        apiKey: string;
        endpoint: string;
        resourceName: string;
        apiVersion: string;
        description: string;
      };
    };
    google: {
      gemini: {
        enabled: boolean;
        apiKey: string;
        model: string;
        description: string;
      };
    };
    anthropic: {
      enabled: boolean;
      apiKey: string;
      model: string;
      description: string;
    };
    postgres: {
      enabled: boolean;
      host: string;
      port: number;
      database: string;
      user: string;
      password: string;
      ssl: boolean;
      description: string;
    };
    cosmosdb: {
      enabled: boolean;
      endpoint: string;
      key: string;
      description: string;
    };
  };
  server: {
    name: string;
    version: string;
    description: string;
  };
}

class ConfigManager {
  private config!: Config;
  private sharedPostgresStore: PostgresStore | null = null;

  constructor() {
    this.loadConfig();
  }

  private loadConfig() {
    try {
      // Always try to find config.json in the project root, regardless of where the bundled code is running
      const projectRoot = process.env.PROJECT_ROOT || process.cwd();
      
      // When running in .mastra/output, we need to go up to find the project root
      let configPath = path.join(projectRoot, 'config.json');
      
      // If we're in the bundled environment, the current working directory might be the project root,
      // but the bundled code is in .mastra/output, so we try both locations
      const possiblePaths = [
        configPath,
        path.join(process.cwd(), 'config.json'),
        path.join(process.cwd(), '..', '..', 'config.json')
      ];
      
      let configFile = '';
      let actualPath = '';
      
      for (const possiblePath of possiblePaths) {
        try {
          configFile = readFileSync(possiblePath, 'utf-8');
          actualPath = possiblePath;
          break;
        } catch (error) {
          // Continue to next path
        }
      }
      
      if (!configFile) {
        throw new Error('config.json not found. Please ensure config.json exists in the project root.');
      }
      
      this.config = JSON.parse(configFile);
      
      // Override with environment variables if they exist
      this.mergeEnvironmentVariables();
      
      console.log('📁 Configuration loaded successfully');
      this.logEnabledServices();
    } catch (error) {
      console.error('❌ Failed to load config.json:', error);
      throw new Error('Configuration file is required. Please create config.json in the project root.');
    }
  }

  private mergeEnvironmentVariables() {
    // Allow environment variables to override config values
    if (process.env.FIRECRAWL_API_KEY) {
      this.config.services.firecrawl.apiKey = process.env.FIRECRAWL_API_KEY;
      this.config.services.firecrawl.enabled = true;
    }
    
    if (process.env.SPORTSDATA_API_KEY) {
      this.config.services.sportsdata.apiKey = process.env.SPORTSDATA_API_KEY;
    }
    
    if (process.env.AZURE_SEARCH_ENDPOINT) {
      this.config.services.azure.search.endpoint = process.env.AZURE_SEARCH_ENDPOINT;
      this.config.services.azure.search.apiKey = process.env.AZURE_SEARCH_API_KEY || '';
      this.config.services.azure.search.indexName = process.env.AZURE_SEARCH_INDEX_NAME || '';
      this.config.services.azure.search.enabled = !!(process.env.AZURE_SEARCH_ENDPOINT && process.env.AZURE_SEARCH_API_KEY);
    }
    
    if (process.env.AZURE_OPENAI_ENDPOINT) {
      this.config.services.azure.openai.endpoint = process.env.AZURE_OPENAI_ENDPOINT;
      this.config.services.azure.openai.apiKey = process.env.AZURE_API_KEY || process.env.AZURE_OPENAI_API_KEY || '';
      this.config.services.azure.openai.resourceName = process.env.AZURE_RESOURCE_NAME || process.env.AZURE_OPENAI_RESOURCE_NAME || '';
      this.config.services.azure.openai.apiVersion = process.env.AZURE_OPENAI_API_VERSION || '2024-02-01';
      this.config.services.azure.openai.enabled = true;
    }
    
    if (process.env.GEMINI_API_KEY) {
      this.config.services.google.gemini.apiKey = process.env.GEMINI_API_KEY;
      this.config.services.google.gemini.model = process.env.GEMINI_MODEL || 'gemini-2.5-pro';
      this.config.services.google.gemini.enabled = true;
    }
    
    if (process.env.ANTHROPIC_API_KEY) {
      this.config.services.anthropic.apiKey = process.env.ANTHROPIC_API_KEY;
      this.config.services.anthropic.model = process.env.ANTHROPIC_MODEL || 'claude-4-sonnet-20250514';
      this.config.services.anthropic.enabled = true;
    }
    
    if (process.env.POSTGRES_HOST) {
      this.config.services.postgres.host = process.env.POSTGRES_HOST;
      this.config.services.postgres.port = parseInt(process.env.POSTGRES_PORT || '5432');
      this.config.services.postgres.database = process.env.POSTGRES_DATABASE || '';
      this.config.services.postgres.user = process.env.POSTGRES_USER || '';
      this.config.services.postgres.password = process.env.POSTGRES_PASSWORD || '';
      this.config.services.postgres.ssl = process.env.POSTGRES_SSL === 'true';
      this.config.services.postgres.enabled = !!(process.env.POSTGRES_HOST && process.env.POSTGRES_DATABASE);
    }
    
    if (process.env.COSMOS_DB_ENDPOINT) {
      this.config.services.cosmosdb.endpoint = process.env.COSMOS_DB_ENDPOINT;
      this.config.services.cosmosdb.key = process.env.COSMOS_DB_KEY || '';
      this.config.services.cosmosdb.enabled = !!(process.env.COSMOS_DB_ENDPOINT && process.env.COSMOS_DB_KEY);
    }
  }

  private logEnabledServices() {
    const enabledServices = [];
    
    if (this.config.services.firecrawl.enabled) enabledServices.push('🕷️  Firecrawl (web scraping)');
    if (this.config.services.sportsdata.enabled) enabledServices.push('⚾ SportsData APIs');
    if (this.config.services.azure.search.enabled) enabledServices.push('🔍 Azure Search');
    if (this.config.services.azure.openai.enabled) enabledServices.push('🧠 Azure OpenAI');
    if (this.config.services.google.gemini.enabled) enabledServices.push('💎 Google Gemini');
    if (this.config.services.anthropic.enabled) enabledServices.push('🤖 Anthropic Claude');
    if (this.config.services.postgres.enabled) enabledServices.push('🗄️  PostgreSQL');
    if (this.config.services.cosmosdb.enabled) enabledServices.push('🌌 Cosmos DB');
    
    if (enabledServices.length > 0) {
      console.log('✅ Enabled services:');
      enabledServices.forEach(service => console.log(`   ${service}`));
    } else {
      console.log('⚠️  No external services configured - only basic tools available');
    }
  }

  get(): Config {
    return this.config;
  }

  isServiceEnabled(service: string): boolean {
    const keys = service.split('.');
    let current: any = this.config.services;
    
    for (const key of keys) {
      current = current[key];
      if (!current) return false;
    }
    
    return current.enabled === true;
  }

  getServiceConfig(service: string): any {
    const keys = service.split('.');
    let current: any = this.config.services;
    
    for (const key of keys) {
      current = current[key];
      if (!current) return null;
    }
    
    return current;
  }

  getSharedPostgresStore(): PostgresStore {
    if (!this.sharedPostgresStore) {
      const postgresConfig = this.getServiceConfig('postgres');
      // Use connection string format for cleaner configuration
      const connectionString = `postgresql://${encodeURIComponent(postgresConfig.user)}:${encodeURIComponent(postgresConfig.password)}@${postgresConfig.host}:${postgresConfig.port}/agentmemory`;
      
      this.sharedPostgresStore = new PostgresStore({
        connectionString,
        // Optional: specify SSL configuration if needed
        ssl: postgresConfig.ssl ? { rejectUnauthorized: false } : false,
      });
    }
    return this.sharedPostgresStore;
  }
}

export const configManager = new ConfigManager(); 