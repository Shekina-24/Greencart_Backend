# Gunicorn configuration file
import multiprocessing

max_requests = 5000
max_requests_jitter = 100
log_file = "-"
bind = "0.0.0.0"
timeout = 30
num_cpus = multiprocessing.cpu_count()
workers = num_cpus + 1
worker_class = "uvicorn.workers.UvicornWorker"
