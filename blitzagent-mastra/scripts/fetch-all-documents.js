import { SearchClient, AzureKeyCredential } from '@azure/search-documents';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

// ES module compatible __dirname equivalent
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configuration from your existing setup
const AZURE_SEARCH_ENDPOINT = "https://blitz-ai-search.search.windows.net";
const AZURE_SEARCH_API_KEY = "LcU87PCPYwAUa8jMxAYo6AqNNr538wRmc1v1LUg36NAzSeACYRk2";
const INDEX_NAME = "blitz-mlb-index";

async function fetchAllDocuments() {
  try {
    console.log(`🔍 Connecting to Azure AI Search...`);
    console.log(`📍 Endpoint: ${AZURE_SEARCH_ENDPOINT}`);
    console.log(`📁 Index: ${INDEX_NAME}`);

    // Create SearchClient
    const searchClient = new SearchClient(
      AZURE_SEARCH_ENDPOINT,
      INDEX_NAME,
      new AzureKeyCredential(AZURE_SEARCH_API_KEY)
    );
    
    console.log(`📊 Fetching all documents from ${INDEX_NAME}...`);
    
    // Search for all documents with a wildcard query
    // Using '*' to match all documents and setting a high count
    const results = await searchClient.search('*', {
      searchMode: 'all',
      top: 1000, // Maximum allowed per page
      skip: 0,
      includeCount: true
    });
    
    console.log(`📈 Total documents found: ${results.count}`);
    
    // Collect all results
    const allDocuments = [];
    let documentCount = 0;
    
    for await (const result of results.results) {
      allDocuments.push(result.document);
      documentCount++;
      
      // Log progress every 50 documents
      if (documentCount % 50 === 0) {
        console.log(`📄 Processed ${documentCount} documents...`);
      }
    }
    
    console.log(`✅ Successfully fetched ${allDocuments.length} documents`);
    
    // If we expect 203 documents but got fewer, might need pagination
    if (allDocuments.length < results.count) {
      console.log(`⚠️  Note: Retrieved ${allDocuments.length} documents out of ${results.count} total`);
      console.log(`⚠️  Azure Search may require pagination for full results`);
    }
    
    // Prepare output data
    const outputData = {
      metadata: {
        indexName: INDEX_NAME,
        endpoint: AZURE_SEARCH_ENDPOINT,
        totalDocuments: allDocuments.length,
        totalCountReported: results.count,
        fetchedAt: new Date().toISOString(),
        expectedDocuments: 203
      },
      documents: allDocuments
    };
    
    // Save to JSON file
    const outputPath = path.join(__dirname, '..', 'blitz-mlb-index-documents.json');
    fs.writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
    
    console.log(`💾 Documents saved to: ${outputPath}`);
    console.log(`📊 Summary:`);
    console.log(`   - Total documents: ${allDocuments.length}`);
    console.log(`   - Expected: 203`);
    console.log(`   - Status: ${allDocuments.length === 203 ? '✅ Complete' : `⚠️  Partial (${allDocuments.length}/203)`}`);
    
    // Show sample of document structure
    if (allDocuments.length > 0) {
      console.log(`📝 Sample document structure:`);
      const sampleDoc = allDocuments[0];
      console.log(`   Fields: ${Object.keys(sampleDoc).join(', ')}`);
      
      // If it has the fields we expect from the database.ts file
      if (sampleDoc.UserPrompt) {
        console.log(`   Sample UserPrompt: "${sampleDoc.UserPrompt.substring(0, 100)}..."`);
      }
    }
    
    return outputData;
    
  } catch (error) {
    console.error('❌ Error fetching documents:', error);
    
    if (error.message.includes('403')) {
      console.error('🔑 Authentication failed. Please check your API key.');
    } else if (error.message.includes('404')) {
      console.error('🔍 Index not found. Please check the index name.');
    } else if (error.message.includes('network')) {
      console.error('🌐 Network error. Please check your connection.');
    }
    
    throw error;
  }
}

// Handle pagination if needed to get all 203 documents
async function fetchAllDocumentsWithPagination() {
  try {
    console.log(`🔍 Connecting to Azure AI Search with pagination...`);
    
    const searchClient = new SearchClient(
      AZURE_SEARCH_ENDPOINT,
      INDEX_NAME,
      new AzureKeyCredential(AZURE_SEARCH_API_KEY)
    );
    
    const allDocuments = [];
    let skip = 0;
    const pageSize = 50; // Smaller page size for reliability
    let hasMore = true;
    
    while (hasMore) {
      console.log(`📄 Fetching page ${Math.floor(skip / pageSize) + 1} (documents ${skip + 1}-${skip + pageSize})...`);
      
      const results = await searchClient.search('*', {
        searchMode: 'all',
        top: pageSize,
        skip: skip,
        includeCount: true
      });
      
      let pageCount = 0;
      for await (const result of results.results) {
        allDocuments.push(result.document);
        pageCount++;
      }
      
      console.log(`   Retrieved ${pageCount} documents from this page`);
      
      // Check if we should continue
      hasMore = pageCount === pageSize && allDocuments.length < 203;
      skip += pageSize;
      
      // Safety check to avoid infinite loops
      if (skip > 1000) {
        console.log(`⚠️  Safety limit reached at ${skip} skip value`);
        break;
      }
    }
    
    console.log(`✅ Total documents fetched with pagination: ${allDocuments.length}`);
    
    // Prepare output data
    const outputData = {
      metadata: {
        indexName: INDEX_NAME,
        endpoint: AZURE_SEARCH_ENDPOINT,
        totalDocuments: allDocuments.length,
        fetchedAt: new Date().toISOString(),
        expectedDocuments: 203,
        method: 'pagination'
      },
      documents: allDocuments
    };
    
    // Save to JSON file
    const outputPath = path.join(__dirname, '..', 'blitz-mlb-index-documents-paginated.json');
    fs.writeFileSync(outputPath, JSON.stringify(outputData, null, 2));
    
    console.log(`💾 Documents saved to: ${outputPath}`);
    console.log(`📊 Final Summary:`);
    console.log(`   - Total documents: ${allDocuments.length}`);
    console.log(`   - Expected: 203`);
    console.log(`   - Status: ${allDocuments.length === 203 ? '✅ Complete' : allDocuments.length > 203 ? '⚠️  More than expected' : `⚠️  Partial (${allDocuments.length}/203)`}`);
    
    return outputData;
    
  } catch (error) {
    console.error('❌ Error with paginated fetch:', error);
    throw error;
  }
}

// Main execution
async function main() {
  console.log(`🚀 Starting document fetch from ${INDEX_NAME}...`);
  
  try {
    // Try the simple approach first
    console.log(`\n=== Attempt 1: Single request ===`);
    const result1 = await fetchAllDocuments();
    
    // If we didn't get all 203 documents, try pagination
    if (result1.documents.length !== 203) {
      console.log(`\n=== Attempt 2: Paginated requests ===`);
      await fetchAllDocumentsWithPagination();
    }
    
    console.log(`\n🎉 Document fetch completed successfully!`);
    
  } catch (error) {
    console.error(`\n❌ Failed to fetch documents:`, error.message);
    process.exit(1);
  }
}

// Run if this file is executed directly
if (process.argv[1] === __filename) {
  main();
}

export { fetchAllDocuments, fetchAllDocumentsWithPagination }; 