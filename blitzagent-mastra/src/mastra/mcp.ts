import { MCPClient } from '@mastra/mcp';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Get the path to the Python MCP server
const mcpServerPath = join(__dirname, '../../../mcp');

export const mcp = new MCPClient({
  servers: {
    blitzAgent: {
      command: 'bash',
      args: [join(mcpServerPath, 'start.sh')],
      env: {
        // Pass any environment variables your Python MCP server needs
        PYTHONPATH: join(mcpServerPath, 'src'),
      },
      logger: (logMessage) => {
        console.log(`[MCP ${logMessage.level}] ${logMessage.message}`);
      },
      enableServerLogs: true,
    },
  },
  timeout: 60000, // 60 second timeout
}); 