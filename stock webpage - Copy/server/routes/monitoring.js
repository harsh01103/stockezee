import express from 'express';
import os from 'os';

export const monitoringRouter = express.Router();

/**
 * GET /monitoring/health
 * Simple health check endpoint
 */
monitoringRouter.get('/health', (req, res) => {
    res.json({ status: 'UP', timestamp: new Date().toISOString() });
});

/**
 * GET /monitoring/metrics
 * Prometheus/Grafana compatible metrics endpoint
 */
monitoringRouter.get('/metrics', (req, res) => {
    const memoryUsage = process.memoryUsage();
    
    // Simple Prometheus format response
    const metrics = `
# HELP node_memory_rss_bytes Resident set size in bytes.
# TYPE node_memory_rss_bytes gauge
node_memory_rss_bytes ${memoryUsage.rss}
# HELP node_memory_heap_total_bytes Total heap size in bytes.
# TYPE node_memory_heap_total_bytes gauge
node_memory_heap_total_bytes ${memoryUsage.heapTotal}
# HELP node_memory_heap_used_bytes Used heap size in bytes.
# TYPE node_memory_heap_used_bytes gauge
node_memory_heap_used_bytes ${memoryUsage.heapUsed}
# HELP system_cpu_load System load average over 1 minute.
# TYPE system_cpu_load gauge
system_cpu_load ${os.loadavg()[0]}
# HELP system_total_memory_bytes Total system memory.
# TYPE system_total_memory_bytes gauge
system_total_memory_bytes ${os.totalmem()}
# HELP system_free_memory_bytes Free system memory.
# TYPE system_free_memory_bytes gauge
system_free_memory_bytes ${os.freemem()}
    `.trim();

    res.set('Content-Type', 'text/plain');
    res.send(metrics);
});
