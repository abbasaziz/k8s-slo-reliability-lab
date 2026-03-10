from fastapi import FastAPI, HTTPException
import os
import psycopg2
import threading
import time
from prometheus_client import Counter, Histogram, generate_latest
from fastapi.responses import Response
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    
# 1. Setup the Tracer
resource = Resource(attributes={
    SERVICE_NAME: "fastapi-service"
})

provider = TracerProvider(resource=resource)
# Point this to the Jaeger agent we just deployed in K8s
jaeger_exporter = JaegerExporter(
    agent_host_name="reliability-jaeger-agent.observability",
    agent_port=6831,
)
provider.add_span_processor(BatchSpanProcessor(jaeger_exporter))
trace.set_tracer_provider(provider)

# 2. Instrument the App (After creating the FastAPI 'app' object)
# FastAPIInstrumentor.instrument_app(app) # Run this after app = FastAPI()
app = FastAPI()
FastAPIInstrumentor.instrument_app(app)
# Global state to track DB health
db_connected = False

def check_db_connectivity():
    """Background task to update db_connected status"""
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
        except Exception:
            db_connected = False
        time.sleep(1)  # Check every 5 seconds

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start_time = time.time()
    response = await call_next(request)
    latency = time.time() - start_time

    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()

    REQUEST_LATENCY.labels(
        endpoint=request.url.path
    ).observe(latency)

    return response

@app.on_event("startup")
def startup_event():
    # Start the background health checker
    thread = threading.Thread(target=check_db_connectivity, daemon=True)
    thread.start()

# Metrics
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

@app.get("/live")
def live():
    # Liveness: Is the Python process running?
    return {"status": "alive"}

@app.get("/ready")
def readiness_check():
    # Readiness: Can we actually talk to the DB?
    if db_connected:
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Database unreachable")

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type="text/plain")

@app.get("/stress")
def stress():
    total = sum(range(10_000_000))
    return {"done": total}
