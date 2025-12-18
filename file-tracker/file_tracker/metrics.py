"""Prometheus metrics server for file-tracker service."""
import logging
import os

from aiohttp import web
from prometheus_client import generate_latest


async def metrics_handler(request):
    """Handler for /metrics endpoint exposing Prometheus client metrics."""
    return web.Response(body=generate_latest(), content_type="text/plain")


async def start_metrics_server(host='0.0.0.0', port=None):
    """Start a basic Prometheus metrics server exposing client metrics."""
    port = port or int(os.getenv('FILE_TRACKER_METRICS_PORT', '9091'))
    app = web.Application()
    app.router.add_get('/metrics', metrics_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()
    logging.info("Metrics server started on %s:%s", host, port)
    return runner
