#!/usr/bin/env node

import fs from 'fs';
import path from 'path';

function copyAssets() {
  const outputDir = '.mastra/output';
  
  // Ensure directories exist
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  
  try {
    // Copy config.json
    if (fs.existsSync('config.json')) {
      fs.copyFileSync('config.json', path.join(outputDir, 'config.json'));
      console.log('✅ Copied config.json');
    }
    
    console.log('🎉 All assets copied successfully');
  } catch (error) {
    console.error('❌ Error copying assets:', error.message);
    process.exit(1);
  }
}

copyAssets(); 