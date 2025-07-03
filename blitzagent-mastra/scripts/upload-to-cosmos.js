import { CosmosClient } from '@azure/cosmos';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

// ES module compatible __dirname equivalent
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Cosmos DB configuration from your existing setup
const COSMOS_DB_ENDPOINT = "https://blitz-queries.documents.azure.com:443/";
const COSMOS_DB_KEY = "TOcf9Xq2Dk4vWkrIwmaiPh31TNwEqfl3AfxZiwErtDzoxQnL5RA8qxtXEKemorcVoLBv7zJ92Ut6ACDbVxU80w==";
const DATABASE_NAME = "sports";
const COLLECTION_NAME = "mlb";

async function uploadDocumentsToCosmos() {
  try {
    console.log(`🚀 Starting upload to Cosmos DB...`);
    console.log(`📍 Endpoint: ${COSMOS_DB_ENDPOINT}`);
    console.log(`📁 Database: ${DATABASE_NAME}`);
    console.log(`📄 Collection: ${COLLECTION_NAME}`);

    // Initialize Cosmos DB client
    const cosmosClient = new CosmosClient({
      endpoint: COSMOS_DB_ENDPOINT,
      key: COSMOS_DB_KEY
    });

    // Get database and container references
    const database = cosmosClient.database(DATABASE_NAME);
    
    // Create container if it doesn't exist
    console.log(`🔧 Ensuring container '${COLLECTION_NAME}' exists...`);
    const { container } = await database.containers.createIfNotExists({
      id: COLLECTION_NAME,
      partitionKey: { paths: ['/id'] }
    });

    // Read the JSON file
    const jsonFilePath = path.join(__dirname, '..', 'blitz-mlb-index-documents.json');
    console.log(`📖 Reading documents from: ${jsonFilePath}`);
    
    if (!fs.existsSync(jsonFilePath)) {
      throw new Error(`JSON file not found: ${jsonFilePath}`);
    }

    const jsonData = JSON.parse(fs.readFileSync(jsonFilePath, 'utf8'));
    const documents = jsonData.documents;
    
    console.log(`📊 Found ${documents.length} documents to upload`);

    let successCount = 0;
    let errorCount = 0;
    const errors = [];

    // Process documents in batches for better performance
    const batchSize = 10;
    const totalBatches = Math.ceil(documents.length / batchSize);

    for (let batchIndex = 0; batchIndex < totalBatches; batchIndex++) {
      const start = batchIndex * batchSize;
      const end = Math.min(start + batchSize, documents.length);
      const batch = documents.slice(start, end);

      console.log(`📦 Processing batch ${batchIndex + 1}/${totalBatches} (documents ${start + 1}-${end})...`);

      // Process batch in parallel
      const promises = batch.map(async (doc, index) => {
        try {
          // Extract only the required fields
          const cosmosDocument = {
            id: doc.id,
            UserPrompt: doc.UserPrompt,
            Query: doc.Query,
            UserPromptVector: doc.UserPromptVector,
            QueryVector: doc.QueryVector,
            // Add metadata
            uploadedAt: new Date().toISOString(),
            sourceIndex: "blitz-mlb-index"
          };

          await container.items.create(cosmosDocument);
          return { success: true, id: doc.id };
        } catch (error) {
          return { 
            success: false, 
            id: doc.id, 
            error: error.message,
            docIndex: start + index
          };
        }
      });

      // Wait for batch to complete
      const results = await Promise.all(promises);
      
      // Count results
      const batchSuccess = results.filter(r => r.success).length;
      const batchErrors = results.filter(r => !r.success);
      
      successCount += batchSuccess;
      errorCount += batchErrors.length;
      errors.push(...batchErrors);

      console.log(`   ✅ Success: ${batchSuccess}, ❌ Errors: ${batchErrors.length}`);

      // Show any errors in this batch
      if (batchErrors.length > 0) {
        console.log(`   🔍 Batch errors:`);
        batchErrors.forEach(err => {
          console.log(`     - Document ${err.docIndex + 1} (${err.id}): ${err.error}`);
        });
      }

      // Small delay between batches to avoid rate limiting
      if (batchIndex < totalBatches - 1) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
    }

    // Final summary
    console.log(`\n🎉 Upload completed!`);
    console.log(`📊 Summary:`);
    console.log(`   ✅ Successfully uploaded: ${successCount} documents`);
    console.log(`   ❌ Failed uploads: ${errorCount} documents`);
    console.log(`   📈 Success rate: ${((successCount / documents.length) * 100).toFixed(1)}%`);

    if (errors.length > 0) {
      console.log(`\n⚠️  Errors encountered:`);
      
      // Group errors by type
      const errorGroups = {};
      errors.forEach(err => {
        const errorType = err.error.includes('conflict') ? 'Already exists' : 
                         err.error.includes('rate') ? 'Rate limited' :
                         err.error.includes('size') ? 'Document too large' : 'Other';
        
        if (!errorGroups[errorType]) errorGroups[errorType] = [];
        errorGroups[errorType].push(err);
      });

      Object.entries(errorGroups).forEach(([type, errs]) => {
        console.log(`   ${type}: ${errs.length} documents`);
        if (errs.length <= 5) {
          errs.forEach(err => console.log(`     - ${err.id}: ${err.error}`));
        } else {
          errs.slice(0, 3).forEach(err => console.log(`     - ${err.id}: ${err.error}`));
          console.log(`     ... and ${errs.length - 3} more`);
        }
      });

      // Save error details to file
      const errorLogPath = path.join(__dirname, '..', 'cosmos-upload-errors.json');
      fs.writeFileSync(errorLogPath, JSON.stringify({
        uploadedAt: new Date().toISOString(),
        totalDocuments: documents.length,
        successCount,
        errorCount,
        errors
      }, null, 2));
      console.log(`📝 Error details saved to: ${errorLogPath}`);
    }

    return {
      totalDocuments: documents.length,
      successCount,
      errorCount,
      errors
    };

  } catch (error) {
    console.error('❌ Critical error during upload:', error);
    
    if (error.message.includes('401') || error.message.includes('403')) {
      console.error('🔑 Authentication failed. Please check your Cosmos DB credentials.');
    } else if (error.message.includes('404')) {
      console.error('🔍 Database or container not found. Please check the configuration.');
    } else if (error.message.includes('network')) {
      console.error('🌐 Network error. Please check your connection.');
    }
    
    throw error;
  }
}

// Function to check existing documents and handle duplicates
async function checkExistingDocuments() {
  try {
    console.log(`🔍 Checking for existing documents in Cosmos DB...`);
    
    const cosmosClient = new CosmosClient({
      endpoint: COSMOS_DB_ENDPOINT,
      key: COSMOS_DB_KEY
    });

    const database = cosmosClient.database(DATABASE_NAME);
    const container = database.container(COLLECTION_NAME);

    // Query to count existing documents
    const querySpec = {
      query: 'SELECT VALUE COUNT(1) FROM c'
    };

    const { resources } = await container.items.query(querySpec).fetchAll();
    const existingCount = resources[0] || 0;
    
    console.log(`📊 Found ${existingCount} existing documents in ${COLLECTION_NAME} collection`);
    
    if (existingCount > 0) {
      console.log(`⚠️  Warning: Collection already contains documents.`);
      console.log(`   This upload will attempt to create new documents with the same IDs.`);
      console.log(`   Conflicts will be reported as errors.`);
    }

    return existingCount;

  } catch (error) {
    console.log(`ℹ️  Could not check existing documents (collection may not exist yet): ${error.message}`);
    return 0;
  }
}

// Main execution function
async function main() {
  console.log(`🚀 Starting Cosmos DB upload process...`);
  
  try {
    // Check for existing documents
    await checkExistingDocuments();
    
    console.log(`\n=== Starting Document Upload ===`);
    const result = await uploadDocumentsToCosmos();
    
    console.log(`\n✅ Upload process completed successfully!`);
    console.log(`📊 Final Stats: ${result.successCount}/${result.totalDocuments} documents uploaded`);
    
    if (result.errorCount === 0) {
      console.log(`🎯 Perfect! All documents uploaded without errors.`);
    } else {
      console.log(`⚠️  ${result.errorCount} documents had errors (see details above)`);
    }
    
  } catch (error) {
    console.error(`\n❌ Upload process failed:`, error.message);
    process.exit(1);
  }
}

// Run if this file is executed directly
if (process.argv[1] === __filename) {
  main();
}

export { uploadDocumentsToCosmos, checkExistingDocuments }; 