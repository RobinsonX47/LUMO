"""
Gunicorn Production Configuration
Optimized for multi-core servers with proper worker/thread settings
"""

import multiprocessing
import os

# Server socket
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"
backlog = 2048

# Worker processes
# Use 2-4 workers per core (CPU-bound: 2, I/O-bound: 4)
workers = int(os.getenv('GUNICORN_WORKERS', multiprocessing.cpu_count() * 2 + 1))
worker_class = 'sync'  # or 'gevent' for async
worker_connections = 1000
max_requests = 1000  # Restart workers after X requests (prevent memory leaks)
max_requests_jitter = 50  # Add randomness to prevent thundering herd
timeout = 30  # Timeout for worker processes
keepalive = 2

# Threading
threads = int(os.getenv('GUNICORN_THREADS', 2))  # Threads per worker

# Logging
accesslog = '-'  # Log to stdout
errorlog = '-'  # Log to stderr
loglevel = os.getenv('LOG_LEVEL', 'info')
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'lumo'

# Server mechanics
daemon = False  # Run in foreground for container compatibility
pidfile = None
user = None
group = None
tmp_upload_dir = None

# SSL (if needed)
# keyfile = '/path/to/keyfile'
# certfile = '/path/to/certfile'

def on_starting(server):
    """Called just before the master process is initialized."""
    print("=" * 60)
    print("🎬 LUMO Starting in Production Mode")
    print("=" * 60)
    print(f"Workers: {workers}")
    print(f"Threads per worker: {threads}")
    print(f"Bind: {bind}")
    print("=" * 60)

def on_reload(server):
    """Called to recycle workers during a reload."""
    print("🔄 Reloading workers...")

def worker_int(worker):
    """Called when a worker receives the SIGINT or SIGQUIT signal."""
    print(f"⚠️ Worker {worker.pid} interrupted")

def worker_abort(worker):
    """Called when a worker receives the SIGABRT signal."""
    print(f"❌ Worker {worker.pid} aborted")
