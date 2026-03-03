# Kubernetes SLO-Driven Reliability Lab
## Overview
This project demonstrates production-grade SLO monitoring, multi-window burn rate alerting, autoscaling, and failure modeling in Kubernetes.

It simulates a FastAPI service backed by PostgreSQL with:

* Availability SLO (99%)
* Latency SLO (P95 < 300ms)
* Error budget burn rate alerts
* Horizontal Pod Autoscaling
* Alert routing to Slack
* CI/CD pipeline via GitHub Actions

---

## Architecture
User → FastAPI → PostgreSQL
FastAPI → Prometheus → Alertmanager → Slack
HPA scales FastAPI based on CPU

## SLO Definitions
### Availability
99% successful requests.
Error budget: 1%
Burn rate thresholds:
Fast burn: >2x (critical)
Slow burn: >1x (warning)

### Latency
95th percentile latency < 300ms

---

## Failure Simulation
Database outage under load:
* Success rate dropped to 70%
* Burn rate exceeded 7x
* Critical alert fired
* System recovered automatically
* Alert resolved

## CI/CD
On push to main:
* Docker image builds automatically
* Image pushed to DockerHub
* Ready for deployment

---

## Key Learnings
1. Fail-fast readiness prevents cascading failure
2. CPU-based HPA does not understand business health
3. Multi-window burn rate alerts detect reliability risk early
4. Recording rules optimize Prometheus performance

[![Build and Push Docker Image](https://github.com/abbasaziz/k8s-slo-reliability-lab/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/abbasaziz/k8s-slo-reliability-lab/actions/workflows/ci.yaml)