          ┌───────────┐
          │   Client  │
          └─────┬─────┘
                │
        ┌───────▼────────┐
        │    FastAPI     │
        └───────┬────────┘
                │
        ┌───────▼────────┐
        │   PostgreSQL   │
        └────────────────┘

FastAPI exposes /metrics → Prometheus
Prometheus evaluates SLO rules → Alertmanager
Alertmanager → Slack
HPA scales FastAPI based on CPU