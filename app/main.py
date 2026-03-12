import os
import time
import logging
import threading
import psycopg2
from fastapi import FastAPI, HTTPException, Response

# OpenTelemetry Core Imports
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, ConsoleSpanExporter

# Exporters & Instrumentation
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

# Prometheus Metrics
from prometheus_client import Counter, Histogram, generate_latest

# --- LOGGING SETUP ---
# Forces debug logs so we can see OpenTelemetry internal events in 'kubectl logs'
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# 1. Identity
resource = Resource.create({SERVICE_NAME: "fastapi-service"})
provider = TracerProvider(resource=resource)

# 2. Exporters
otlp_exporter = OTLPSpanExporter(endpoint="http://reliability-jaeger-collector.observability.svc.cluster.local:4318/v1/traces")
provider.add_span_processor(SimpleSpanProcessor(otlp_exporter))
provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

# 3. Set Global Provider
trace.set_tracer_provider(provider)

# --- METRICS DEFINITIONS ---
REQUEST_COUNT = Counter(
    "app_requests_total",
    "Total HTTP Requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "app_request_latency_seconds",
    "Request latency",
    ["endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0)
)

# --- APP INITIALIZATION ---
app = FastAPI(title="Reliability Lab - Tracing & SLOs")

FastAPIInstrumentor.instrument_app(app)

# Global state for background DB checker
db_connected = False

def check_db_connectivity():
    """Background task to continuously verify Database health."""
    global db_connected
    while True:
        try:
            conn = psycopg2.connect(
                host="postgres",
                database=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                connect_timeout=2
            )
            conn.close()
            db_connected = True
        except Exception as e:
            logger.error(f"Database connectivity failed: {e}")
            db_connected = False
        time.sleep(5)

@app.on_event("startup")
def startup_event():
    thread = threading.Thread(target=check_db_connectivity, daemon=True)
    thread.start()
    logger.info("Background tasks started.")

# --- MIDDLEWARE ---
@app.middleware("http")
async def metrics_middleware(request, call_next):
    """Calculates latency and increments Prometheus counters for every request."""
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        endpoint=request.url.path
    ).observe(duration)

    return response

# --- ENDPOINTS ---

@app.get("/live")
def live():
    """Liveness probe: Checks if the process is responsive."""
    return {"status": "alive"}

@app.get("/ready")
def readiness_check():
    """Readiness probe: Checks if the DB connection is healthy."""
    if db_connected:
        return {"status": "ready"}
    raise HTTPException(status_code=503, detail="Database unreachable")

@app.get("/metrics")
def metrics():
    """Exposes Prometheus metrics for scraping."""
    return Response(generate_latest(), media_type="text/plain")

@app.get("/stress")
def stress():
    """Simulates a heavy workload and creates a manual span for verification."""
    tracer = trace.get_tracer(__name__)
    # We create a manual child span to ensure Jaeger captures the internal work
    with tracer.start_as_current_span("heavy-calculation-task"):
        total = sum(range(10_000_000))
        return {"done": total, "result": "Calculated 10M sum"}