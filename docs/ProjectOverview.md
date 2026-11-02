# Project Overview

### 1.1 Project Information

- Project name: LivingDocs — Design and Implementation of an AI-Assisted Self-Updating Document System for Engineering Teams
- Group name: Gau Gau
- Software type: Web App & AI System

### 1.2 Project Team

 

| **Full Name** | **Role** | **Email** |
| --- | --- | --- |
| Nguyễn Dương Quốc Tiến | Leader | <tienndq5464@ut.edu.vn> |
|   | Member |   |
|   | Member |   |
|   | Member |   |
|   | Member |   |
| Nguyễn Văn Chiến | Lecturer | <chiennv@ut.edu.vn> |

### 2. Product Background

        Recent empirical research highlights that documentation drift is a widespread problem in software engineering. Tan et al. analyzed more than 3,000 GitHub repositories and reported that 28.9% of the most popular GitHub projects currently contain outdated code references, while 82.3% have experienced documentation drift during their development history. Furthermore, outdated documentation typically remains undetected for 4.2–4.7 years, demonstrating that documentation inconsistencies persist for extended periods without automated detection.

To address this issue, the researchers proposed DOCER, an automated tool that detects outdated code element references by comparing documentation with the evolution history of source code. DOCER successfully identifies references to removed or renamed classes, methods, and variables within README files and GitHub Wikis.

Despite these contributions, several research gaps remain.

- Limited documentation coverage.

- Limited semantic understanding.

- Limited code-document analysis accuracy.

- Limited CI/CD integration and automation.

These limitations indicate the need for an intelligent documentation maintenance system capable of understanding semantic code evolution, supporting multiple documentation formats, providing accurate code-document linkage, and continuously monitoring documentation within modern software development workflows.

Based on these limitations, the group of students proposed  project **LivingDocs**, an AI-assisted documentation maintenance system designed to continuously detect and resolve documentation drift during software development

### 3. Existing Systems

### 3.1 DOCER (Automated Code Reference Detection Tool)

- **Link:** [https://github.com/wesleytanws/DOCER\_tool](https://github.com/wesleytanws/DOCER_tool)
- **Description:** An automated research tool designed to detect outdated code element references by comparing documentation against the evolution history of source code.
- **Actors:** Software Developers / Contributors, Open-Source Maintainers, Software Engineering Researchers.
- **Features:**
    - Extracts code element references (classes, methods, variables) from documentation.
    - Compares documentation content with source code revision history.
    - Detects broken references caused by removed or renamed code elements within `README.md` and GitHub Wikis.
- **Pros:**
    - Automated Entity-Level Drift Detection:Automatically extracts and checks references to code entities (classes, methods, variables) against git evolution history to identify obsolete documentation accurately when code is deleted or renamed.
    - Empirically Validated on Large-Scale Datasets: Tested and proven effective across a massive dataset of over 3,000 popular GitHub repositories, demonstrating high practical relevance for open-source software maintenance.
    - Non-Intrusive Workflow: Operates directly on existing text-based documentation files (`README.md`, GitHub Wikis) without requiring developers to modify source code, add special annotations, or change their build configuration.
    - Precise Historical Commit Tracing**:** Traces code changes across commit histories to pinpoint the exact code modification or Pull Request that caused the documentation drift..
- **Cons:**
    - Limited documentation coverage: Existing approaches mainly focus on text-based documentation such as README files and GitHub Wikis. They do not support richer documentation formats including architecture diagrams, images, PDFs, or videos, which would require techniques such as Optical Character Recognition (OCR) and multimodal document understanding.
    - Limited semantic understanding: Current techniques primarily detect documentation drift when code elements are deleted or renamed. They cannot identify semantic inconsistencies caused by behavioral changes, architectural refactoring, or modified relationships between software components while the referenced code elements still exist.
    - Limited code-document analysis accuracy: DOCER relies mainly on regular expressions to extract code references from documentation. This approach may produce false positives, especially for comments, changelogs, and language-specific constructs. More robust parsing techniques such as Abstract Syntax Tree (AST) analysis can provide higher precision and richer structural information.
    - Limited CI/CD integration and automation: Existing approaches generally require developers to execute documentation analysis manually. They are not deeply integrated into modern Continuous Integration and Continuous Deployment (CI/CD) workflows to automatically detect documentation drift immediately after source code changes occur.

### 3.2 Swimm & Mintlify (Developer-Centric Documentation Platforms)

- **Link:** [https://swimm.io](https://swimm.io/) / [https://mintlify.com](https://mintlify.com/)
- **Description:** Swimm and Mintlify are modern commercial documentation platforms designed to integrate technical documentation directly into the developer workflow. Swimm couples documentation directly to source code snippets within repositories, triggering alerts during Pull Requests when referenced code locations are modified. Mintlify focuses on developer-facing documentation portals and API references, automatically generating interactive pages from OpenAPI specifications and code comments. Both tools aim to reduce the friction of maintaining technical documentation by embedding doc management into IDEs (VS Code, JetBrains) and Git version control workflows.
- **Actors:** Software Engineers, Technical Leads, Technical Writers, Product Managers.
- **Features:**
    - Code-Coupled Snippets: Links specific lines of documentation directly to underlying source code elements within git repositories.
    - Automated PR Checks: Runs automated status checks on GitHub Pull Requests to flag code changes affecting documented code snippets.
    - IDE Extensions: Integrates with VS Code and JetBrains IDEs, enabling developers to read, update, and create documentation directly alongside code.
    - Interactive API Documentation: Automatically parses OpenAPI/Swagger specifications and inline code annotations to render interactive API references.
- **Pros:**
    - Modern, intuitive user interface providing an exceptional developer experience and customizable documentation portals.
    - Seamless integration with modern development environments, IDEs, and Git repository ecosystems.
    - Proactively alerts developers during code reviews when modified code impacts linked documentation.
- **Cons:**
    - High Enterprise Cost: Proprietary commercial products requiring paid subscription plans that scale per user or per repository, limiting accessibility for open-source or budget-constrained projects.
    - Lack of Deep AST Semantic Parsing: Relies on line-range matching and comment tags rather than Abstract Syntax Tree (AST) structural analysis, failing to detect deep semantic logic changes when syntax remains similar.
    - No Multimodal / OCR Capabilities: Cannot extract or synchronize information from visual assets such as architecture diagrams, flowcharts, images, or PDF documents.
    - Missing Multi-Role Governance: Lacks a structured 2-tier review workflow (Developer --\> Staff Reviewer →  Manager Approval) with role-attributed change logs needed for corporate auditability.

### 4. Business Opportunity

        Modern software engineering teams face widespread documentation drift, resulting in significant developer inefficiency, onboarding bottlenecks, and compounding technical debt. This creates a compelling business opportunity to develop an intelligent documentation maintenance system that automates drift detection and resolution through Abstract Syntax Tree (AST) parsing, multimodal document processing, and seamless CI/CD integration. The proposed LivingDocs system will target software development organizations and enterprise engineering teams, competing in the developer tooling market by delivering continuous semantic synchronization and a structured multi-role governance workflow that current static doc generators and commercial platforms fail to offer.

### 5. Software Product Vision

         For software engineering teams and enterprise development organizations seeking to eliminate documentation drift, LivingDocs is an AI-assisted web-based system that enables developers to automatically detect, verify, and resolve code-doc inconsistencies through Abstract Syntax Tree (AST) parsing, multimodal OCR, and automated CI/CD integration. Technical leads and managers can efficiently review grounding evidence, monitor documentation health, and enforce quality standards via a structured 2-tier approval workflow. Unlike static documentation generators or basic regex-based detectors, LivingDocs reduces manual maintenance overhead, improves semantic accuracy across repositories, and prevents obsolete technical debt. By embedding continuous synchronization into version control workflows, the system also lays the foundation for automated documentation governance and long-term engineering productivity.

### 6. Project Scope & Limitations

### 6.1 Major Features

     ● **FE1. Workspace & Version Control Integration:** Enables developers to connect GitHub accounts via GitHub OAuth, manage repository workspaces, configure GitHub Apps, track Pull Request/commit ingesting status, and manage webhook triggers for real-time repository synchronization.

     ●** FE2. AST-Based AI Documentation Generation:** Automatically reads source code structure using Abstract Syntax Tree (AST) analysis to parse code entities (classes, methods, endpoints, parameters, return values, dependencies), identifies coverage gaps, and generates structured draft documentation according to assigned templates.

     ● **FE3. Automatic Documentation Update on Code Change:** Automatically triggers AI update workflows whenever source code changes in a Pull Request or commit, generates updated documentation drafts, provides side-by-side version diff comparisons, and allows developers to accept, edit, regenerate, or rollback versions.

     ● **FE4. Documentation Drift Detection & Semantic Analysis:** Detects documentation inconsistencies using AST parsing and RAG/LLM analysis; classifies drift into Referential, Signature, and Semantic categories; assigns severity levels (Low, Medium, High, Critical); and attaches grounding evidence (code diffs, commit hashes, ticket IDs).

    **● FE5. Multimodal Document & Visual Asset Processing:** Supports non-textual documentation formats by using Optical Character Recognition (OCR) and Vision-LLMs to extract context from architecture diagrams, flowcharts, images, and PDF files to verify consistency against source code.

    ● **FE6. Automated CI/CD Pipeline & Merge Policy Integration:** Integrates deeply into GitHub Actions CI workflows to execute automated documentation checks on Pull Requests, with configurable PR merge policies (warn or block PR merge on critical drift).

    ●** FE7. Governed 2-Tier Review & Approval Workflow:** Implements a structured review pipeline where Staff Reviewers perform first-level checks against code and templates, add section comments, and forward to Managers for final approval before publishing or committing to the repository.

    ● **FE8. Role-Attributed Change Log & Version Audit Trail: **Maintains a complete, tamper-evident version history timeline for every document, attributing every change to the acting role (AI, Staff, or Manager) with timestamps, triggering commits, and full version rollback capabilities.

    ●** FE9. Interactive Code-vs-Doc Diff & Grounding Evidence Viewer: **Provides visual side-by-side comparison interfaces between modified source code diffs and suggested documentation patches, allowing reviewers to verify grounding evidence (source file paths, line numbers, and commits).

   ** ● FE10. Documentation Governance & Health Analytics:** Provides Technical Leads with a central dashboard to monitor documentation freshness, coverage metrics, total drift status, dependency graphs for impact analysis, and compliance report exports.

    ●** FE11. Dynamic Template Management Library:** Allows Technical Leads to create, clone, edit, and enforce documentation templates (API References, READMEs, Module Guides, Onboarding Guides, ADRs) with placeholders mapped directly to code entities and AI formatting constraints.

    **● FE12. Knowledge Base & Code-Doc Dependency Search:** Features full-text and semantic vector search across documentation collections, displaying interactive doc-to-code relationships and bidirectional navigation between documents and source files.

    ● **FE13. System Administration & AI Engine Configuration:** Provides Administrators with RBAC permission management, third-party service integration settings (GitHub, GitLab, Jira, Slack), supported language selection, and AI parameter tuning (LLM models, embedding models, confidence thresholds, token budgets).

### 6.2 Limitations & Exclusions

**     ●** **LI-01:** The system strictly focuses on GitHub as the primary source control platform for current implementation; integrations with GitLab and Azure DevOps are planned as future architectural extensions.

**     ● LI-02:** Multimodal document processing covers architecture diagrams, images, and PDF files, but explicitly excludes processing of video and audio formats.

**     ●** **LI-03:** Direct unmonitored repository commits by the AI Engine are excluded; all generated or updated documentation requires human-in-the-loop approval (Staff review and Manager approval) unless explicitly configured for auto-apply by a Manager.

**     ● LI-04:** Performance SLAs for Pull Request drift detection (under 2 minutes) are bounded to repositories containing up to 100,000 lines of source code and up to 20 concurrent Pull Request events.

**     ● LI-05:** Automated semantic drift analysis and code entity extraction are restricted to programming languages explicitly configured and supported by the AST parser within the system administration settings.

**     ● ** **LI-06:** Third-party service integrations (Jira, Slack) are scoped exclusively to metadata extraction for grounding evidence (ticket references) and event notifications, without replacing full project management functions.

**    ● ** **LI-07:** Real-time continuous verification requires active cloud connectivity for Webhooks and GitHub Actions CI/CD workflows, excluding fully isolated or air-gapped offline environments.
