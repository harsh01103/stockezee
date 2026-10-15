import { modelEvaluator } from './modelEvaluator.js';

async function runTests() {
    console.log('Testing Model Evaluator...');

    const rawSignal = { symbol: 'TSLA', strategy: 'MOMENTUM', confidence: 85, predicted_move: 5.0 };
    const standardized = modelEvaluator.standardizeSignal(rawSignal);
    console.assert(standardized.symbol === 'TSLA', 'Should standardize symbol');

    const pastSignals = [
        { symbol: 'AAPL', predicted_move: 2.0, confidence_score: 80 },
        { symbol: 'MSFT', predicted_move: -1.5, confidence_score: 70 }
    ];

    const marketData = {
        'AAPL': { actual_move: 3.0 }, // Hit (both positive)
        'MSFT': { actual_move: 1.0 }  // Miss (predicted negative, actual positive)
    };

    const evaluation = modelEvaluator.evaluatePerformance(pastSignals, marketData);
    console.assert(evaluation.hit_rate === 50, 'Hit rate should be 50%');
    console.assert(evaluation.signals[0].is_hit === true, 'AAPL should be a hit');
    console.assert(evaluation.signals[1].is_hit === false, 'MSFT should be a miss');

    console.log('All Model Evaluator tests passed!');
}

runTests().catch(console.error);
