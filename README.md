# Spamphibian

Spamphibian is in a very early development stage. It is a scalable and low-latency spam detection and management service for GitLab, designed to identify, classify, and handle potential spam activities using machine learning models. The service is implemented in Python and uses the GitLab API and Redis.

## Table of Contents

- [Spamphibian](#spamphibian)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Limitations](#limitations)
  - [Installation](#installation)
    - [Using Helm](#using-helm)
    - [Using Docker](#using-docker)
    - [Using Docker Compose](#using-docker-compose)
    - [Using Python](#using-python)
  - [Monitoring](#monitoring)
  - [License](#license)

## Overview

Spamphibian uses various components to combat spam, including GitLab API, Redis queues, and multiple jobs and services.

This is the planned architecture of Spamphibian, but it is subject to change:

```mermaid
  flowchart TB
    subgraph "GitLab Components"
      GH[GitLab System Hook]
      API[GitLab API]
    end

    subgraph "Redis Components"
      Q1[GitLab Item Fetch Queue]
      Q2[User Trust and Verification Queue]
      CQ[Classification Queue]
      DQ[Deletion Queue]
      VRU[Verified Renku Users List]
    end

    subgraph "Spam Management System"
      subgraph "Jobs"
        SC[Snippet Check Job]
        VU[Verified Users Retriever Job]
      end
      subgraph "Services"
        ES[Event Service]
        FS[GitLab Item Fetch Service]
        TV[User Trust and Verification Service]
        CS[Classification Service]
        DS[Deletion Service]
        subgraph "Other Components"
          S3[S3 Bucket]
          L[Logs]
          TED[Trusted Email Domains List]
          ML[Classifier Model]
        end
      end
    end

    GH -->|Triggered on item create/update| ES
    SC -->|Runs Periodically| ES
    VU -->|Updated Periodically| VRU
    ES --> Q1
    Q1 --> FS
    FS -->|Get Item| API
    FS -->|Add Item To Queue| Q2
    Q2 --> TV
    TED --> TV 
    VRU --> TV 
    VU -->|Get Verified Users| API
    TV -->|If Not Trusted Or Verified| CQ
    CQ --> CS
    CS -->|If Item Is Spam| DQ
    CS -->|Classification Result| L
    DQ --> DS
    DS -->|Delete Item from GitLab| API
    DS -->|Set Item to Private in GitLab| API
    CS -->|Store Evaluated Content| S3
    S3 -->|Download Model On Startup| ML
    CS <-->|Classification| ML
    
    style GH fill:#E24329,stroke:#333,stroke-width:4px
    style API fill:#E24329,stroke:#333,stroke-width:4px
    style ES fill:#645EB6,stroke:#333,stroke-width:4px
    style SC fill:#E46991,stroke:#333,stroke-width:4px
    style FS fill:#645EB6,stroke:#333,stroke-width:4px
    style TV fill:#645EB6,stroke:#333,stroke-width:4px
    style CS fill:#645EB6,stroke:#333,stroke-width:4px
    style DS fill:#645EB6,stroke:#333,stroke-width:4px
    style VU fill:#E46991,stroke:#333,stroke-width:4px
    style Q1 fill:#009A6A,stroke:#333,stroke-width:4px
    style Q2 fill:#009A6A,stroke:#333,stroke-width:4px
    style CQ fill:#009A6A,stroke:#333,stroke-width:4px
    style DQ fill:#009A6A,stroke:#333,stroke-width:4px
    style VRU fill:#009A6A,stroke:#333,stroke-width:4px
```

## Limitations

Currently, Spamphibian only notifies about potential spam activities. It does not take any action on its own. This is planned for a future release.

Additionally, Spamphibian requires a model service to be running. This service is responsible for serving the machine learning models used for classification. An example model service is provided in `models/flask_service.py`. Releasing a basic, general-use model image is planned for the future.

## Installation

Ensure smooth sailing with `spamphibian` by following these concise steps.

Prerequisites:

- GitLab instance
- GitLab admin token
- Slack webhook URL
- Redis instance (this can be the same as the one used by GitLab, but use a dedicated database. Gitlab usually uses database 0, so use 1, for example)
- Model service (see `models/flask_service.py` for an example)
  
### Using Helm

   ```bash
   helm repo add renku https://swissdatasciencecenter.github.io/helm-charts/
   helm install spamphibian renku/spamphibian -f your-values-file.yaml
   ```

### Using Docker

   ```bash
   docker run --name spamphibian -e REDIS_HOST="localhost" -e GITLAB_URL="https://gitlab.example.com" -e GITLAB_TOKEN="glpat-abc" -e SLACK_WEBHOOK_URL="https://hooks.slack.com/services/a/b/c" -e MODEL_URL="http://localhost:5001" -p 8000:8000 renku/spamphibian
   ```

### Using Docker Compose

   ```bash
   docker-compose up
   ```

### Using Python

1. Install prerequisites.

    ```bash
    pip install -r requirements.txt
    ```

2. Set environment variables.

    ```bash
    export GITLAB_URL="https://gitlab.example.com"
    export GITLAB_TOKEN="glpat-abc"
    export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/a/b/c"
    export REDIS_HOST="localhost"
    export MODEL_URL="http://localhost:5001"
    ```

3. Run the service.

    ```bash
    python main.py
    ```

After Spamphibian is up and running, create a GitLab System Hook through the GitLab admin portal. Point the hook to the `/events` endpoint of Spamphibian. The hook should be triggered on all system-level spam-related events.

## Monitoring

Spamphibian exposes a Prometheus endpoint on port 8000 at `/metrics`.

## License

Spamphibian is licensed under the [Apache 2.0 license](LICENSE).
