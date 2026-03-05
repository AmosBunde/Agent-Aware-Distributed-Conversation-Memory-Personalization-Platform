# 🧠 Agent-Aware Distributed Conversation Memory & Personalization Platform

A production-style backend system that **stores, retrieves, personalizes, and serves long-term conversational context** for millions of AI users with low latency and strong reliability guarantees.

---

## What It Does

- **Conversation Memory** — Stores full conversation history with structured metadata extraction (skills, preferences, entities)
- **Semantic Retrieval** — Fast vector-similarity search over millions of past conversations via pgvector
- **Personalization Pipelines** — Converts raw interaction history into user embeddings and ranked context bundles
- **Session Memory** — Short-term Redis-backed session state with TTL management
- **Long-term Knowledge Storage** — PostgreSQL + DynamoDB durable storage with tiered retrieval
- **Relevance Scoring** — Re-ranks retrieved memories by recency, relevance, and user preference signal
- **Reliability** — Caching tiers, fallback retrieval, per-user rate limiting, circuit breakers, failure isolation
- **APIs** — Conversation history retrieval, memory mutation, real-time personalization signals

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AI Agent / ChatGPT Backend                      │
│              (calls this platform to get/store context)              │
└───────────────────────────────┬─────────────────────────────────────┘
                                │ gRPC / REST
┌───────────────────────────────▼─────────────────────────────────────┐
│                         API Gateway (FastAPI)                        │
│          Auth · Rate Limiting · Circuit Breaker · OTEL               │
└──┬─────────────────┬──────────────────┬──────────────────┬──────────┘
   │                 │                  │                  │
┌──▼──────────┐ ┌────▼────────┐ ┌──────▼──────┐ ┌────────▼────────┐
│   Memory    │ │Personalizatn│ │  Embedding  │ │    Session      │
│   Service   │ │  Service    │ │  Service    │ │    Service      │
│             │ │             │ │             │ │                 │
│ - Store     │ │ - User emb. │ │ - Encode    │ │ - Active ctx    │
│ - Retrieve  │ │ - Context   │ │ - Similarity│ │ - TTL mgmt      │
│ - Mutate    │ │   bundles   │ │ - pgvector  │ │ - Fast recall   │
│ - Rank      │ │ - Pref sig. │ │             │ │                 │
└──┬──────────┘ └────┬────────┘ └──────┬──────┘ └────────┬────────┘
   │                 │                  │                  │
   └─────────────────┴──────────────────┴──────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                    Apache Kafka / Cloud Pub/Sub                       │
│  memory.stored  memory.retrieved  embedding.requested  session.ended  │
└──┬──────────────────────────────────────────────────────────────────┘
   │
┌──▼──────────────────────────────────────────────────────────────────┐
│               Persistence & Vector Storage Layer                     │
│  Redis (hot cache, sessions)  PostgreSQL+pgvector (memories+vectors) │
│  DynamoDB (event log, scale)  S3/Blob/GCS (raw conversation archive)│
└──┬──────────────────────────────────────────────────────────────────┘
   │
┌──▼──────────────────────────────────────────────────────────────────┐
│         Observability: Prometheus · Grafana · Jaeger (OTEL)          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Core Services | Python 3.11, FastAPI, gRPC |
| Event Streaming | Apache Kafka (AWS MSK / Azure Event Hubs / GCP Pub/Sub) |
| Hot Cache | Redis 7 (Cluster mode) |
| Durable Storage | PostgreSQL 15 + pgvector extension |
| Document Store | DynamoDB (AWS) / CosmosDB (Azure) / Firestore (GCP) |
| Vector Search | pgvector (self-hosted) or Pinecone (managed) |
| Embeddings | OpenAI `text-embedding-3-small` / sentence-transformers |
| Orchestration | Kubernetes + Helm |
| IaC | Terraform 1.7+ |
| CI/CD | GitHub Actions |
| Observability | Prometheus + Grafana + OpenTelemetry + Jaeger |
| Object Storage | S3 / Azure Blob / GCS |

---

## Project Structure

```
conv-memory-platform/
├── services/
│   ├── memory-service/          # Store, retrieve, rank conversation memories
│   ├── personalization-service/ # User embeddings, preference signals, context bundles
│   ├── embedding-service/       # Encode text → vectors, pgvector similarity search
│   ├── session-service/         # Short-term Redis-backed session state
│   └── gateway/                 # API Gateway (auth, rate limiting, circuit breaker)
├── infrastructure/
│   └── terraform/
│       ├── modules/
│       │   ├── networking/      # VPC / VNet / GCP VPC
│       │   ├── eks/             # AWS EKS cluster
│       │   ├── gke/             # GCP GKE cluster
│       │   ├── aks/             # Azure AKS cluster
│       │   ├── kafka/           # MSK / Event Hubs / Pub/Sub
│       │   ├── vectordb/        # PostgreSQL + pgvector
│       │   ├── cache/           # Redis / ElastiCache / Memorystore
│       │   └── storage/         # S3 / Blob / GCS
│       └── environments/
│           ├── aws/
│           ├── azure/
│           └── gcp/
├── helm/                        # Kubernetes Helm chart
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                     # DB init, seed, migration scripts
├── .github/workflows/           # CI/CD pipeline
├── docker-compose.yml
└── Makefile
```

---

## Local Development

### Prerequisites

- Docker Desktop ≥ 4.20 + Docker Compose v2
- Python 3.11+
- Make
- OpenAI API key (for embedding service) or use the local sentence-transformer fallback

### 1. Clone & configure

```bash
git clone https://github.com/YOUR_USERNAME/conv-memory-platform.git
cd conv-memory-platform
cp .env.example .env
# Edit .env — at minimum, set OPENAI_API_KEY (or EMBEDDING_BACKEND=local)
```

### 2. Start the full stack

```bash
make dev
```

| Service | URL |
|---|---|
| API Gateway | http://localhost:8000/docs |
| Memory Service | http://localhost:8001/docs |
| Personalization | http://localhost:8002/docs |
| Embedding Service | http://localhost:8003/docs |
| Session Service | http://localhost:8004/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Jaeger | http://localhost:16686 |
| Kafka UI | http://localhost:8080 |
| Prometheus | http://localhost:9090 |
| pgAdmin | http://localhost:5050 |

### 3. Store a conversation memory

```bash
curl -X POST http://localhost:8000/api/v1/memories \
  -H "Content-Type: application/json" \
  -H "X-User-ID: user-123" \
  -d '{
    "session_id": "sess-abc",
    "role": "user",
    "content": "I prefer concise answers. I am a senior Python engineer.",
    "metadata": {"intent": "preference_setting"}
  }'
```

### 4. Retrieve relevant context for a new conversation turn

```bash
curl "http://localhost:8000/api/v1/memories/user-123/context?query=python+coding+help&top_k=5"
```

### 5. Get personalization signals

```bash
curl "http://localhost:8000/api/v1/personalization/user-123/profile"
```

---

## Deploy to AWS

### Prerequisites
AWS CLI v2, Terraform 1.7+, kubectl, helm

### 1. Bootstrap Terraform state

```bash
cd infrastructure/terraform/environments/aws
chmod +x bootstrap.sh && ./bootstrap.sh
```

### 2. Configure & apply

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit: aws_region, cluster_name, db_password, openai_api_key
terraform init && terraform plan -out=tfplan && terraform apply tfplan
```

**Provisions:** VPC (3 AZs + NAT) · EKS 1.29 (m5.2xlarge, 3–30 nodes) · Amazon MSK (3-broker Kafka) · RDS PostgreSQL 15 + pgvector · ElastiCache Redis (cluster mode) · DynamoDB (on-demand) · S3 conversation archive · ECR repositories · IAM/IRSA roles

### 3. Deploy application

```bash
aws eks update-kubeconfig --name conv-memory-prod --region us-east-1
make build-push AWS_ACCOUNT_ID=123456789012 AWS_REGION=us-east-1
helm upgrade --install conv-memory ./helm \
  --namespace conv-memory --create-namespace \
  --values helm/values-aws.yaml \
  --set image.tag=$(git rev-parse --short HEAD)
```

---

## Deploy to Azure

### Prerequisites
Azure CLI, Terraform 1.7+, kubectl, helm

### 1. Authenticate

```bash
az login
az ad sp create-for-rbac --name "conv-memory-sp" --role Contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID --sdk-auth > azure-credentials.json
export ARM_CLIENT_ID=$(jq -r .clientId azure-credentials.json)
export ARM_CLIENT_SECRET=$(jq -r .clientSecret azure-credentials.json)
export ARM_SUBSCRIPTION_ID=$(jq -r .subscriptionId azure-credentials.json)
export ARM_TENANT_ID=$(jq -r .tenantId azure-credentials.json)
```

### 2. Deploy

```bash
cd infrastructure/terraform/environments/azure
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

**Provisions:** Resource Group + VNet · AKS 1.29 (Standard_D8s_v3, autoscale) · Azure Event Hubs (Kafka-compatible) · PostgreSQL Flexible Server + pgvector · Azure Cache for Redis · CosmosDB (Mongo API) · Azure Container Registry · Blob Storage

### 3. Deploy application

```bash
az aks get-credentials --resource-group conv-memory-rg --name conv-memory-aks
az acr login --name convmemoryacr
make build-push ACR_NAME=convmemoryacr
helm upgrade --install conv-memory ./helm --values helm/values-azure.yaml
```

---

## Deploy to GCP

### Prerequisites
gcloud CLI, Terraform 1.7+, kubectl, helm

### 1. Enable APIs

```bash
gcloud services enable container.googleapis.com sqladmin.googleapis.com \
  redis.googleapis.com pubsub.googleapis.com storage.googleapis.com \
  artifactregistry.googleapis.com firestore.googleapis.com
```

### 2. Deploy

```bash
cd infrastructure/terraform/environments/gcp
cp terraform.tfvars.example terraform.tfvars
terraform init && terraform apply
```

**Provisions:** VPC + Private subnets + Cloud NAT · GKE (e2-standard-8, autoscale) · Cloud Pub/Sub · Cloud SQL PostgreSQL 15 (REGIONAL HA) + pgvector · Memorystore Redis 7 · Firestore (native mode) · GCS archive · Artifact Registry

### 3. Deploy application

```bash
gcloud container clusters get-credentials conv-memory-gke --region us-central1
gcloud auth configure-docker us-central1-docker.pkg.dev
make build-push GCP_PROJECT=YOUR_PROJECT GCP_REGION=us-central1
helm upgrade --install conv-memory ./helm --values helm/values-gcp.yaml
```

---

## API Reference

### Memory API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/memories` | Store a conversation turn |
| GET | `/api/v1/memories/{user_id}` | Retrieve conversation history |
| GET | `/api/v1/memories/{user_id}/context` | Semantic search: top-K relevant memories |
| DELETE | `/api/v1/memories/{user_id}/{memory_id}` | Delete a specific memory |
| PATCH | `/api/v1/memories/{user_id}/{memory_id}` | Mutate memory metadata |

### Personalization API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/v1/personalization/{user_id}/profile` | User preference profile |
| GET | `/api/v1/personalization/{user_id}/context-bundle` | Ranked context bundle for next AI turn |
| POST | `/api/v1/personalization/{user_id}/signal` | Ingest explicit preference signal |

### Session API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/v1/sessions` | Create new session |
| GET | `/api/v1/sessions/{session_id}` | Get active session context |
| PATCH | `/api/v1/sessions/{session_id}` | Update session state |
| DELETE | `/api/v1/sessions/{session_id}` | End session, flush to long-term |

---

## Running Tests

```bash
make test-unit          # Fast, no infrastructure
make test-integration   # Requires: make dev
make test-e2e           # Full black-box end-to-end
make coverage           # HTML report, target ≥80%
```

---

## Dashboards

Grafana (http://localhost:3001) ships with pre-built dashboards:

- **Memory Operations** — store/retrieve latency, cache hit rate, vector search p99
- **Session Health** — active sessions, TTL expiry rate, Redis memory pressure
- **Personalization Pipeline** — embedding throughput, profile update lag
- **Kafka Throughput** — consumer lag per topic, partition balance
- **API Gateway** — per-endpoint p50/p95/p99, error rate, rate limit hits
