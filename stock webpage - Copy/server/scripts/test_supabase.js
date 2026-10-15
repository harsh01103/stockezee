import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../.env') }); // Root .env

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_SERVICE_ROLE;

console.log("URL:", supabaseUrl);
console.log("Key starts with:", supabaseKey.substring(0, 15));

const supabase = createClient(supabaseUrl, supabaseKey);

async function test() {
    console.log("Testing insert into security_master...");
    const { data, error } = await supabase.from('security_master').upsert({
        instrument_id: 'NSE_TEST1234',
        symbol: 'TEST1234',
        company_name: 'Test Company',
        exchange: 'NSE',
        is_active: true
    });
    
    if (error) {
        console.error("Error:", error);
    } else {
        console.log("Insert successful! Data:", data);
        
        console.log("Testing delete...");
        const del = await supabase.from('security_master').delete().eq('symbol', 'TEST1234');
        console.log("Delete error?", del.error);
    }
}

test();
