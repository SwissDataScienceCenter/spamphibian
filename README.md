# Spamphibian

Spamphibian is in a very early development stage. It is a scalable and low-latency spam detection and management service for GitLab, designed to identify, classify, and handle potential spam activities using machine learning models. The service is implemented in Python and uses the GitLab API and Redis.

## Table of Contents

- [Spamphibian](#spamphibian)
  - [Table of Contents](#table-of-contents)
  - [Overview](#overview)
  - [Installation](#installation)
  - [Usage](#usage)
  - [Contributing](#contributing)
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

## Installation

Coming soon!

## Usage

Spamphibian is in a very early development stage. It is not yet ready for production use and currently requires manual configuration and bespoke components to be built to get it working. The following steps are necessary to get it working:

The following environment variables are required:

- `GITLAB_URL`: The URL of the GitLab instance to connect to.
- `GITLAB_TOKEN`: The token to use to authenticate with the GitLab instance, which must have admin privileges.
- `SLACK_WEBHOOK_URL`: The URL of the Slack webhook to use to send notifications.

Install the dependencies in `requirements.txt` using `pip install -r requirements.txt`.

A local Redis instance is required to run the service, which can be started using `docker run --env=ALLOW_EMPTY_PASSWORD=yes --runtime=runc -p 6379:6379 -d bitnami/redis:latest`, for example.

A web service that evaluates the data from GitLab is required to run the service. An example evaluation service can be found in `classification_service/flask_service.py`. Beware that this example service requires a preprocessing pipeline and Keras model to be present and will not work out of the box currently. A simple script training model will be published in the future, so these components can be built easily using your own GitLab data.

A system hook must be configured on the GitLab instance to send notifications to the service. The URL of the Spamphibian service must be configured in the system hook.

Currently, Spamphibian only evaluates `user_create` and `user_rename` events.

Spamphibian can then be started using `python main.py`.

## Contributing

Contributions are welcome! Please read the contributing guidelines in the `CONTRIBUTING.md` file before making any contributions.

## License

Spamphibian is under the [MIT License](LICENSE).
