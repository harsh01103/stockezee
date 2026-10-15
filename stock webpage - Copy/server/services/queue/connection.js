import { Redis } from 'ioredis';
import dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
dotenv.config({ path: path.join(__dirname, '../../.env') });

const redisUrl = process.env.REDIS_URL || 'redis://127.0.0.1:6379';

const connectionOptions = {
    maxRetriesPerRequest: null,
    enableReadyCheck: false,
    lazyConnect: true,
    retryStrategy(times) {
        if (times > 3) {
            console.warn('[Redis] Max connection retries reached. Running without Redis.');
            return null;
        }
        return Math.min(times * 1000, 3000);
    }
};

// If using TLS (Upstash), ioredis handles it via the rediss:// protocol automatically
export const connection = new Redis(redisUrl, connectionOptions);

connection.on('error', (err) => {
    // Only log once or at warning level
    if (err.code !== 'ECONNREFUSED') {
        console.error('[Redis] Connection Error:', err.message);
    }
});

connection.on('connect', () => {
    console.log('[Redis] Connected successfully.');
});

