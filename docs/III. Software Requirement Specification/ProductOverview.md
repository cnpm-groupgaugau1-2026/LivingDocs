<img width="1086" height="700" alt="image" src="https://github.com/user-attachments/assets/cf181fba-048f-4dfe-955a-61a4e9c5566e" />

The LivingDocs — AI-Assisted Self-Updating Document System (LivingDocs) is a comprehensive web-based platform designed to automate documentation drift detection, streamline technical documentation maintenance, and enforce continuous 100% synchronization between source code evolution and project knowledge for engineering teams

Operational Environment:

Platform: Web-based application accessible via standard modern web browsers (Google Chrome, Microsoft Edge, Mozilla Firefox, Apple Safari) on desktop and tablet devices.

Connectivity: The system requires a continuous, high-speed Internet connection to receive real-time GitHub Webhook payloads, interact with cloud-based Large Language Model (LLM) APIs, and maintain repository synchronization (no offline mode supported).

Infrastructure: Deployed on cloud container infrastructure (Docker Compose / AWS EC2) using a microservice architecture. The core backend services run on Java Spring Boot, the AI Engine runs on Python FastAPI, and data services utilize PostgreSQL (with pgvector extension enabled), Redis caching, and Apache Kafka event streaming.

Anticipated Users:

Internal Users:

Developer (Author): Connects repositories, triggers AI documentation generation, reviews automated update drafts, and resolves documentation drift alerts.

Staff (Reviewer): Performs Tier-1 technical reviews of AI-generated documentation drafts, verifies source code consistency, and checks template compliance.

Manager (Approver): Conducts Tier-2 final approvals, controls publishing and repository commit actions, and configures PR merge block policies.

Technical Lead (Document Owner): Designs dynamic documentation templates, manages document collections, and monitors repository health and coverage metrics.

Administrator: Manages user accounts, configures Role-Based Access Control (RBAC), sets up third-party integration keys, and tunes AI processing parameters.

External Systems & Integrations:

GitHub Platform: Handles OAuth2 authentication, GitHub App repository access, Webhook event streaming, Pull Request status checks, and automated .md commits.

External AI Services: Provides Large Language Model (OpenAI LLM), Vision-LLM (OCR for architectural diagrams), and vector embedding generation.

Third-Party Services: Integrates with Jira for metadata extraction and Slack for real-time notification alerts.

Constraints & Assumptions:

Language: The web application user interface supports bilingual accessibility in both Vietnamese and English.

Compliance & Security: System operations strictly enforce Role-Based Access Control (RBAC), TLS 1.3/HTTPS network encryption, AES-256 encryption for API keys/tokens, and maintain an immutable, tamper-evident audit log for corporate compliance auditing.

Integrations: Direct API integration with GitHub OAuth2/Apps for repository access, alongside REST APIs for Jira ticket references and Slack messaging.

Scope Limitations:

Platform Limitation: Version 1.0 focuses exclusively on GitHub as the primary version control platform; integration with GitLab and Azure DevOps is reserved for future releases.

Multimodal Limitation: Processes text, architectural diagrams, flowcharts, visual images, and PDF documents; explicitly excludes audio and video media files.

Governance Limitation: Unsupervised direct commits to repositories by the AI Engine are strictly prohibited; all AI-generated or auto-updated documentation requires mandatory human review (Staff Review and Manager Approval) before publishing, unless explicitly configured for auto-apply by a Manager.

Performance SLA Limitation: Performance SLA for Pull Request drift analysis (< 2 minutes) applies to software repositories containing up to 100,000 lines of source code under a maximum load of 20 concurrent Pull Request events.

Language Parser Scope: Automatic AST entity extraction and semantic drift detection are strictly limited to explicitly configured and supported programming languages (Java, Python, TypeScript).

Third-Party Integration Scope: Jira and Slack integrations are limited to metadata extraction (grounding evidence) and event notifications, without replacing third-party project management functions.

Connectivity Scope: Real-time automated verification requires active internet connectivity for Webhooks and GitHub Actions CI/CD workflows, excluding air-gapped offline environments.

Dependencies:

Depends on the availability, uptime, and rate limits of third-party external services (GitHub REST/GraphQL APIs, OpenAI LLM / Vision APIs, Jira/Slack Webhooks).

Requires a pre-configured PostgreSQL database instance with the pgvector extension enabled, a functional Redis in-memory cache, and a running Apache Kafka message broker.
