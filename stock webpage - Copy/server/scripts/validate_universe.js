import { UniverseBuilder } from '../services/universe/universeBuilder.js';

const builder = new UniverseBuilder();
const universe = await builder.buildDailyUniverse();

// Show stats
const equities = universe.filter(u => u.is_equity);
const etfs = universe.filter(u => u.is_etf);
const nse = universe.filter(u => u.exchange.includes('NSE'));
const bse = universe.filter(u => u.exchange.includes('BSE'));

console.log('\n=== UNIVERSE STATS ===');
console.log(`Total: ${universe.length}`);
console.log(`Equities: ${equities.length}`);
console.log(`ETFs: ${etfs.length}`);
console.log(`NSE: ${nse.length}`);
console.log(`BSE: ${bse.length}`);

// Look for suspicious survivors
const suspicious = universe.filter(u => {
    const sym = u.symbol || '';
    const name = u.company_name || '';
    return /^\d/.test(sym) || /%/.test(name) || /PVT$/.test(name) || /PTC$/.test(name) || /NCD/i.test(name) || /SDL/i.test(name) || /TBILL/i.test(name) || /GOI/i.test(name) || /\d{2,}-\d+-\d+-\d+/.test(name);
});

console.log(`\nSuspicious survivors: ${suspicious.length}`);
if (suspicious.length > 0) {
    console.log('Sample suspicious:');
    suspicious.slice(0, 30).forEach(s => console.log(`  ${s.symbol} | ${s.company_name} | ${s.exchange} | series=${s.series}`));
}

// Validation test cases
const testCases = [
    { query: 'RELIANCE', expect: 'PASS' },
    { query: 'SBIN', expect: 'PASS' },
    { query: 'MON100', expect: 'PASS' },
    { query: 'GS16DEC2030', expect: 'FAIL' },
    { query: '775IRFC33', expect: 'FAIL' },
    { query: '749RJ35', expect: 'FAIL' },
    { query: '182D110626', expect: 'FAIL' },
];

console.log('\n=== VALIDATION ===');
for (const tc of testCases) {
    const found = universe.find(u => u.symbol === tc.query);
    const result = found ? 'FOUND' : 'NOT FOUND';
    const pass = (tc.expect === 'PASS' && found) || (tc.expect === 'FAIL' && !found);
    console.log(`  ${tc.query}: ${result} (expected ${tc.expect}) → ${pass ? '✅ PASS' : '❌ FAIL'}`);
}
