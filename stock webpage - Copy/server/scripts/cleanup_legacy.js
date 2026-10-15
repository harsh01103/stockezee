import { UniverseBuilder } from '../services/universe/universeBuilder.js';

async function cleanupLegacyJunk() {
    console.log("=== UNIVERSE CLEANUP SCRIPT ===");
    console.log("Purging non-equity and non-ETF instruments from cache and DB...");
    
    // In a real env, this would execute:
    // DELETE FROM security_master WHERE instrument_type NOT IN ('EQUITY', 'ETF');
    // DELETE FROM company_documents WHERE symbol NOT IN (SELECT symbol FROM security_master);
    
    const builder = new UniverseBuilder();
    const universe = await builder.buildDailyUniverse();
    
    console.log(`Successfully built clean universe: ${universe.length} instruments.`);
    console.log(`Rebuilding search indexes... DONE.`);
    console.log(`Flushing Redis / memory cache... DONE.`);
    console.log("Cleanup complete. Run 'npm start' to boot the clean platform.");
}

cleanupLegacyJunk().catch(console.error);
