import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../../.env') });

const supabaseUrl = process.env.SUPABASE_URL || process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE;

if (!supabaseUrl || !supabaseKey) {
    console.error('Missing Supabase credentials for SecurityMaster');
}

const supabase = createClient(supabaseUrl, supabaseKey);

/**
 * Service to interact with the security_master table.
 */
export class SecurityMaster {
    /**
     * Get all active symbols in the universe
     */
    static async getActiveUniverse() {
        let allData = [];
        let from = 0;
        let to = 999;
        let hasMore = true;

        while (hasMore) {
            const { data, error } = await supabase
                .from('security_master')
                .select('*')
                .eq('is_active', true)
                .range(from, to);
                
            if (error) {
                console.error('[SecurityMaster] Error fetching universe:', error);
                throw error;
            }

            if (data && data.length > 0) {
                allData = allData.concat(data);
                from += 1000;
                to += 1000;
            }
            if (!data || data.length < 1000) {
                hasMore = false;
            }
        }
        return allData;
    }

    /**
     * Upsert a stock into the security master
     */
    static async upsertSymbol(stockData) {
        const { data, error } = await supabase
            .from('security_master')
            .upsert({
                instrument_id: stockData.instrument_id || `${stockData.exchange || 'NSE'}_${stockData.symbol}`,
                symbol: stockData.symbol,
                company_name: stockData.company_name,
                exchange: stockData.exchange || 'NSE',
                instrument_type: stockData.instrument_type || 'EQUITY',
                sector: stockData.sector,
                industry: stockData.industry,
                market_cap_bucket: stockData.market_cap_bucket,
                is_fno_eligible: stockData.is_fno_eligible || false,
                is_active: stockData.is_active !== undefined ? stockData.is_active : true,
                updated_at: new Date().toISOString()
            }, { onConflict: 'symbol' });

        if (error) {
            console.error(`[SecurityMaster] Error upserting ${stockData.symbol}:`, error);
            throw error;
        }
        return data;
    }

    /**
     * Batch upsert stocks into the security master
     */
    static async upsertSymbolsBatch(stockDataArray) {
        const symbolsInChunk = stockDataArray.map(s => s.symbol);
        const { data: existingData } = await supabase
            .from('security_master')
            .select('symbol, is_active')
            .in('symbol', symbolsInChunk);

        const inactiveSet = new Set();
        if (existingData) {
            for (const row of existingData) {
                if (row.is_active === false) {
                    inactiveSet.add(row.symbol);
                }
            }
        }

        const payload = stockDataArray.map(stockData => ({
            instrument_id: stockData.instrument_id || `${stockData.exchange || 'NSE'}_${stockData.symbol}`,
            symbol: stockData.symbol,
            company_name: stockData.company_name,
            exchange: stockData.exchange || 'NSE',
            instrument_type: stockData.instrument_type || 'EQUITY',
            sector: stockData.sector,
            industry: stockData.industry,
            market_cap_bucket: stockData.market_cap_bucket,
            is_fno_eligible: stockData.is_fno_eligible || false,
            is_active: inactiveSet.has(stockData.symbol) ? false : (stockData.is_active !== undefined ? stockData.is_active : true),
            updated_at: new Date().toISOString()
        }));

        const { data, error } = await supabase
            .from('security_master')
            .upsert(payload, { onConflict: 'symbol' });

        if (error) {
            console.error(`[SecurityMaster] Error batch upserting:`, error);
            throw error;
        }
        return data;
    }
}
