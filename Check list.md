# Check list

Đã hoàn thành :

     ● **FE1. Workspace & Version Control Integration:** Enables developers to connect GitHub accounts via GitHub OAuth, manage repository workspaces, configure GitHub Apps, track Pull Request/commit ingesting status, and manage webhook triggers for real-time repository synchronization.

-Authenticate & Manage Workspace via GitHub OAuth

-GitHub App Integration & Repository Synchronization

-Webhook Handler & Real-time Ingestion Pipeline

     ●** FE2. AST-Based AI Documentation Generation:** Automatically reads source code structure using Abstract Syntax Tree (AST) analysis to parse code entities (classes, methods, endpoints, parameters, return values, dependencies), identifies coverage gaps, and generates structured draft documentation according to assigned templates.

-Multi-language AST Code Entity Parser Engine

-Documentation Coverage Gap Identification Analyzer

-Template-Guided AI Draft Generation Pipeline

     ● **FE3. Automatic Documentation Update on Code Change:** Automatically triggers AI update workflows whenever source code changes in a Pull Request or commit, generates updated documentation drafts, provides side-by-side version diff comparisons, and allows developers to accept, edit, regenerate, or rollback versions.

-Event-Triggered Auto-Update Workflow (PR/Commit)

-Code-vs-Doc Side-by-Side Version Comparison Logic

-Action Handlers (Accept, Edit, Regenerate, Rollback)

     ● **FE4. Documentation Drift Detection & Semantic Analysis:** Detects documentation inconsistencies using AST parsing and RAG/LLM analysis; classifies drift into Referential, Signature, and Semantic categories; assigns severity levels (Low, Medium, High, Critical); and attaches grounding evidence (code diffs, commit hashes, ticket IDs).

-Multi-Category Drift Classifier (Referential, Signature, Semantic)

-Severity Scoring Engine (Low, Medium, High, Critical)

-Grounding Evidence Extraction & Context Attachment Engine

    **● FE5. Multimodal Document & Visual Asset Processing:** Supports non-textual documentation formats by using Optical Character Recognition (OCR) and Vision-LLMs to extract context from architecture diagrams, flowcharts, images, and PDF files to verify consistency against source code.

-Optical Character Recognition (OCR) Engine for Technical Assets

-Vision-LLM Context Extractor (Diagrams, Flowcharts, PDFs)

-Visual Asset - Code Consistency Verification Pipeline

    ● **FE6. Automated CI/CD Pipeline & Merge Policy Integration:** Integrates deeply into GitHub Actions CI workflows to execute automated documentation checks on Pull Requests, with configurable PR merge policies (warn or block PR merge on critical drift).

-GitHub Actions Custom Workflow & Runner Integration

-PR Merge Policy Enforcement Engine (Warn/Block Merge)

    ●** FE7. Governed 2-Tier Review & Approval Workflow:** Implements a structured review pipeline where Staff Reviewers perform first-level checks against code and templates, add section comments, and forward to Managers for final approval before publishing or committing to the repository.

-Staff Review Queue & Code/Template Verification Engine

-Section-level Commenting & Feedback Pipeline

-Manager Approval Workflow & Automated Commit/Publishing

    ● **FE8. Role-Attributed Change Log & Version Audit Trail: **Maintains a complete, tamper-evident version history timeline for every document, attributing every change to the acting role (AI, Staff, or Manager) with timestamps, triggering commits, and full version rollback capabilities.

-Tamper-Evident Version History Database & Storage

-Role Attribution & Trigger Event Traceability Engine

-Full Document Version Rollback Service

    ●** FE9. Interactive Code-vs-Doc Diff & Grounding Evidence Viewer: **Provides visual side-by-side comparison interfaces between modified source code diffs and suggested documentation patches, allowing reviewers to verify grounding evidence (source file paths, line numbers, and commits).

-Side-by-Side Visual Code vs Doc Diff UI Component

-Grounding Evidence Navigator (File Path, Line, Commit Hash)

   ** ● FE10. Documentation Governance & Health Analytics:** Provides Technical Leads with a central dashboard to monitor documentation freshness, coverage metrics, total drift status, dependency graphs for impact analysis, and compliance report exports.

-Centralized Documentation Health Dashboard UI

-Freshness, Coverage & Drift Metrics Aggregator

-Code-Doc Dependency Impact Graph & Compliance Exporter

    ●** FE11. Dynamic Template Management Library:** Allows Technical Leads to create, clone, edit, and enforce documentation templates (API References, READMEs, Module Guides, Onboarding Guides, ADRs) with placeholders mapped directly to code entities and AI formatting constraints.

-Dynamic Template Builder & Placeholder Mapping Engine

-Template Library Manager & Version Control System

-AI Output Formatting Constraints Enforcement Engine

    **● FE12. Knowledge Base & Code-Doc Dependency Search:** Features full-text and semantic vector search across documentation collections, displaying interactive doc-to-code relationships and bidirectional navigation between documents and source files.

-Vector Search & Hybrid RAG Retrieval Engine

-Interactive Bidirectional Navigation UI (Document \<-\> Code Entity)

    ● **FE13. System Administration & AI Engine Configuration:** Provides Administrators with RBAC permission management, third-party service integration settings (GitHub, GitLab, Jira, Slack), supported language selection, and AI parameter tuning (LLM models, embedding models, confidence thresholds, token budgets).

-RBAC User & Permission Management Panel

-Third-Party Service Integration Settings (GitHub, Jira, Slack)

-AI Parameter Tuning Panel (LLM Models, Token Budget, Thresholds)

Chưa làm 

**     ●** **LI-01:** The system strictly focuses on GitHub as the primary source control platform for current implementation; integrations with GitLab and Azure DevOps are planned as future architectural extensions.

**     ● LI-02:** Multimodal document processing covers architecture diagrams, images, and PDF files, but explicitly excludes processing of video and audio formats.

**     ●** **LI-03:** Direct unmonitored repository commits by the AI Engine are excluded; all generated or updated documentation requires human-in-the-loop approval (Staff review and Manager approval) unless explicitly configured for auto-apply by a Manager.

**     ● LI-04:** Performance SLAs for Pull Request drift detection (under 2 minutes) are bounded to repositories containing up to 100,000 lines of source code and up to 20 concurrent Pull Request events.

**     ● LI-05:** Automated semantic drift analysis and code entity extraction are restricted to programming languages explicitly configured and supported by the AST parser within the system administration settings.

**     ● ** **LI-06:** Third-party service integrations (Jira, Slack) are scoped exclusively to metadata extraction for grounding evidence (ticket references) and event notifications, without replacing full project management functions.

**    ● ** **LI-07:** Real-time continuous verification requires active cloud connectivity for Webhooks and GitHub Actions CI/CD workflows, excluding fully isolated or air-gapped offline environments.
