import { Mastra } from '@mastra/core/mastra';
import { PinoLogger } from '@mastra/loggers';
import { sportsInsightsAgent } from './agents/sports-insights-agent';
import { generateQueriesAgent } from './agents/generate-queries-agent';
import { configManager } from './config';

export const mastra = new Mastra({
  agents: { sportsInsightsAgent, generateQueriesAgent },
  storage: configManager.getSharedPostgresStore(),
  logger: new PinoLogger({
    name: 'Mastra',
    level: 'info',
  }),
});
