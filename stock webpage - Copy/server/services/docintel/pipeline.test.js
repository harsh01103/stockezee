import { docIntelPipeline } from './pipeline.js';

async function runTests() {
    console.log('Testing Document Intelligence Pipeline...');

    const mockText = "We are optimistic about Q4 due to our new product launch in Asia. However, supply chain issues remain a risk factor. We are increasing our CapEx for next year.";
    
    // Process filing
    const result = await docIntelPipeline.processFiling('RELIANCE', mockText, 'QUARTERLY_EARNINGS');
    console.assert(result.symbol === 'RELIANCE', 'Symbol should match');
    console.assert(result.sentiment_score > 0, 'Sentiment score should be extracted');
    console.assert(result.growth_catalysts.length > 0, 'Growth catalysts should be extracted');

    // Retrieve filing
    const history = await docIntelPipeline.getCompanyIntel('RELIANCE');
    console.assert(history.length > 0, 'Should return processing history');
    console.assert(history[0].capex_trend === 'INCREASING', 'CapEx trend should match');

    console.log('All DocIntel Pipeline tests passed!');
}

runTests().catch(console.error);
