# Gemma 4 Autonomous Developer Agent
## Business Analysis and System Requirements

> **Project concept:** An offline-capable autonomous AI software engineering agent powered by a post-trained Gemma 4 model.
>
> **Primary capability:** Resolve software engineering issues through repository investigation, targeted code changes, patch generation, and independent test verification.
>
> **Primary deliverable:** A unified Git patch that applies to the original repository snapshot and passes the required independent tests.

---

## Table of Contents

- [1. Executive Summary](#1-executive-summary)
- [2. Business Objectives](#2-business-objectives)
- [3. Stakeholders and Actors](#3-stakeholders-and-actors)
- [4. System Scope and Boundaries](#4-system-scope-and-boundaries)
- [5. System Context and Architecture](#5-system-context-and-architecture)
- [6. User Stories](#6-user-stories)
- [7. Functional Requirements](#7-functional-requirements)
- [8. Non-Functional Requirements](#8-non-functional-requirements)
- [9. Business Rules](#9-business-rules)
- [10. Dataset and Data Requirements](#10-dataset-and-data-requirements)
- [11. End-to-End Workflow](#11-end-to-end-workflow)
- [12. Performance Indicators](#12-performance-indicators)
- [13. Requirements Traceability](#13-requirements-traceability)
- [14. Risks and Mitigations](#14-risks-and-mitigations)
- [15. Recommended Development Priorities](#15-recommended-development-priorities)
- [16. Product Definition](#16-product-definition)
- [17. Strategic Innovation and Research Direction](#17-strategic-innovation-and-research-direction)

---

## 1. Executive Summary

The proposed solution is an **autonomous, offline-capable AI software engineering agent powered by a post-trained Gemma 4 model**. Its purpose is to help developers solve real-world software engineering problems, particularly bugs and feature requests in complex Python repositories, without depending on cloud-based AI services.

The system should be capable of understanding natural-language issue descriptions, navigating unfamiliar codebases, identifying relevant dependencies, analyzing potential causes, modifying source code, and generating patches that resolve reported issues.

The competition is not simply evaluating whether an AI model can generate code. It evaluates whether an AI agent can perform a structured software engineering workflow and produce changes that pass independent automated tests.

### Business vision

**Democratize autonomous software engineering by delivering a reliable coding agent that operates offline on accessible hardware, reduces debugging effort, and accelerates software development while preserving developer control over code changes.**

### Business problem

Current AI coding agents face several challenges:

1. **Cloud dependency:** Many advanced coding assistants require internet access and expensive cloud infrastructure.
2. **Hardware constraints:** Developers without high-end computing resources have limited access to advanced AI coding capabilities.
3. **Codebase complexity:** Small language models can struggle to understand large repositories, dependencies, function relationships, and unfamiliar architectures.
4. **Multi-step reasoning:** Debugging requires more than generating code; it requires investigation, hypothesis formation, implementation, and verification.
5. **Reliability:** AI-generated fixes can introduce regressions, modify unrelated files, or fail to address the underlying issue.
6. **Developer productivity:** Manual repository exploration and debugging consume substantial engineering time.

### Proposed business solution

Develop an autonomous software engineering agent that combines:

- A post-trained Gemma 4 foundation model.
- Specialized repository navigation and code analysis capabilities.
- Graph-based dependency exploration.
- Semantic code retrieval using precomputed embeddings.
- Structured multi-step reasoning.
- Controlled source-code editing.
- Automated testing and patch generation.
- Offline execution within a secure sandbox.

The intended outcome is a system that produces reliable, testable software patches rather than merely suggesting code snippets.

---

## 2. Business Objectives

| ID | Business objective | Expected outcome |
|---|---|---|
| BO-01 | Improve software debugging productivity | Reduce manual investigation and debugging effort |
| BO-02 | Enable offline AI development | Eliminate runtime dependence on cloud APIs |
| BO-03 | Improve codebase understanding | Navigate complex repositories and dependencies |
| BO-04 | Increase patch reliability | Produce fixes that pass independent validation |
| BO-05 | Optimize consumer-hardware accessibility | Make advanced coding assistance more accessible |
| BO-06 | Minimize unnecessary code changes | Generate focused patches addressing root causes |
| BO-07 | Support autonomous workflows | Complete issue-to-patch tasks with limited intervention |
| BO-08 | Maintain reproducibility | Produce traceable and reproducible engineering changes |

---

## 3. Stakeholders and Actors

| Stakeholder | Role | Primary interest |
|---|---|---|
| Software developers | Primary users | Faster debugging and feature implementation |
| Software engineering teams | Organizational users | Productivity and maintenance efficiency |
| Open-source maintainers | Beneficiaries | Faster resolution of reported issues |
| AI researchers | Technical stakeholders | Post-training and agent-reasoning research |
| Kaggle competition organizers | Evaluators | Valid, reproducible, high-scoring submissions |
| Gemma model developers | Model providers | Improved practical capabilities of open models |
| Security and infrastructure teams | Governance stakeholders | Safe, isolated, offline execution |

- **Primary system actor:** Autonomous AI Software Engineering Agent.
- **Primary human stakeholder:** Software developer who delegates an issue to the agent and reviews its proposed patch.

> **Competition distinction:** The competition evaluates automated patch resolution. Human review is a recommended product capability, but it is not specified as a mandatory competition workflow.

---

## 4. System Scope and Boundaries

It is important to distinguish the competition's mandatory scope from the broader product vision.

### 4.1 In-scope capabilities

1. Accept software issue descriptions and optional hints.
2. Analyze unfamiliar Python repositories.
3. Navigate source files and directory structures.
4. Identify relevant functions, classes, modules, and dependencies.
5. Retrieve semantically related code.
6. Analyze caller-callee relationships.
7. Form and evaluate hypotheses about software defects.
8. Generate targeted source-code modifications.
9. Execute commands and targeted tests in the sandbox.
10. Generate unified Git patches.
11. Submit patches for independent validation.
12. Operate without internet access during task execution.

### 4.2 Out-of-scope or optional capabilities

The following are not mandatory requirements in the competition description and may be considered future product capabilities:

- A graphical developer dashboard.
- Cloud-based inference services.
- Integration with GitHub or GitLab issue trackers.
- Automatic merging of generated patches into production branches.
- Automatic deployment.
- Support for every programming language.
- Direct modification of production systems.
- Human approval workflows enforced by the competition harness.

---

## 5. System Context and Architecture

### 5.1 Proposed system context

```text
Software Developer / Benchmark Evaluator
                 |
                 | Issue description, hints, repository task
                 v
       Gemma 4 Developer Agent
                 |
       +---------+----------+
       |         |          |
       v         v          v
 Issue Analyzer  Repository  Code Reasoner
                 Navigator
       |         |          |
       +---------+----------+
                 |
                 v
           Patch Generator
                 |
                 v
       Verification Coordinator
                 |
       +---------+----------+
       |                    |
       v                    v
   Sandbox A             Sandbox B
   Agent workspace       Independent verification
   - Explore repository - Fresh repository snapshot
   - Edit source code   - Apply submitted patch
   - Run targeted tests - Run required tests
   - Create Git patch   - Produce test report
       |                    |
       +---------+----------+
                 |
                 v
       Independently validated
             Git patch

Shared intelligence infrastructure:
- Gemma 4 foundation model
- LoRA adapters
- Code graphs
- Code embeddings
- Agent skills
```

### 5.2 Main system components

| Component | Responsibility |
|---|---|
| Issue Analyzer | Understand the problem statement and identify investigation goals |
| Repository Navigator | Explore files, modules, symbols, and repository structure |
| Code Reasoner | Investigate potential root causes and evaluate hypotheses |
| Patch Generator | Make controlled source-code modifications and create patches |
| Verification Coordinator | Run tests, inspect failures, and submit patches |
| Shared intelligence infrastructure | Provide model inference, adapters, code graphs, embeddings, and reusable skills |

### 5.3 Independent verification

The two-container verification process is especially important: the agent's implementation is evaluated in a fresh environment, not merely accepted because its own sandbox reports success.

- **Sandbox A — Agent workspace:** Repository exploration, code editing, targeted testing, and patch creation.
- **Sandbox B — Verification workspace:** Fresh repository snapshot, independent patch application, and required test execution.

The final deliverable is a unified Git patch that is independently validated against the required tests.

---

## 6. User Stories

User stories describe what stakeholders need from the proposed system and why they need it. They are organized by functional area. `Must` indicates a core requirement; `Should` indicates a desirable capability.

### Epic 1: Issue Understanding and Analysis

| ID | User story | Priority |
|---|---|---|
| US-01 | As a developer, I want to provide a natural-language bug report so that the agent understands the software problem I need solved. | Must |
| US-02 | As a developer, I want to provide optional hints and additional context so that the agent can use relevant information when investigating the issue. | Must |
| US-03 | As a developer, I want the agent to identify the affected functionality so that investigation focuses on relevant components. | Must |
| US-04 | As an AI researcher, I want the agent to distinguish symptoms from potential root causes so that it does not produce superficial fixes. | Must |

**Acceptance criteria**

- The agent receives the problem statement.
- The agent incorporates hints when available.
- The agent identifies relevant repository components.
- The agent produces a reasoned investigation before editing files.

### Epic 2: Repository Navigation and Code Understanding

| ID | User story | Priority |
|---|---|---|
| US-05 | As a developer, I want the agent to inspect repository files so that it can understand the existing implementation. | Must |
| US-06 | As a developer, I want the agent to identify callers and dependencies of relevant functions so that modifications do not break related functionality. | Must |
| US-07 | As a developer, I want the agent to find semantically similar code so that it can discover existing implementation patterns. | Must |
| US-08 | As a developer, I want the agent to explore relationships between multiple code symbols so that it can understand interactions across modules. | Must |
| US-09 | As a developer, I want the agent to respect existing coding conventions so that proposed modifications remain consistent with the repository. | Must |

**Acceptance criteria**

- The agent can read files and inspect directory structures.
- It can use dependency graph information.
- It can retrieve relevant code through semantic similarity.
- It can inspect relationships among identified symbols.
- It can avoid unnecessary exploration of unrelated components.

### Epic 3: Autonomous Software Reasoning

| ID | User story | Priority |
|---|---|---|
| US-10 | As a developer, I want the agent to investigate possible causes of an issue so that it identifies the underlying defect. | Must |
| US-11 | As a developer, I want the agent to formulate and compare multiple repair hypotheses so that it can select an appropriate solution. | Should |
| US-12 | As a developer, I want the agent to understand the consequences of a proposed modification so that it avoids introducing regressions. | Must |
| US-13 | As an AI researcher, I want the agent to perform multi-turn reasoning so that it can solve complex tasks requiring several investigative steps. | Must |
| US-14 | As a developer, I want the agent to recover from tool errors so that temporary execution failures do not immediately terminate the task. | Must |

**Acceptance criteria**

- The agent investigates before editing.
- It uses repository evidence to support its hypotheses.
- It revises its approach when evidence contradicts an initial hypothesis.
- It handles recoverable tool errors.
- It operates within configured execution budgets.

### Epic 4: Code Modification and Patch Generation

| ID | User story | Priority |
|---|---|---|
| US-15 | As a developer, I want the agent to modify existing source files so that it can implement the required fix. | Must |
| US-16 | As a developer, I want the agent to create new source files when necessary so that it can implement new functionality. | Must |
| US-17 | As a developer, I want modifications to be limited to relevant files so that unrelated functionality remains unchanged. | Must |
| US-18 | As a developer, I want the agent to generate a unified Git diff so that the changes can be reviewed and applied. | Must |
| US-19 | As a competition evaluator, I want the agent to submit its patch through the prescribed mechanism so that the evaluation system can extract its changes. | Must |

**Acceptance criteria**

- Existing files can be edited.
- New files can be created.
- Ambiguous or non-unique replacements are handled safely.
- The patch contains relevant source-code changes.
- Test files and protected configuration files are not used to manipulate the evaluation.
- The agent explicitly submits the patch.

### Epic 5: Testing and Verification

| ID | User story | Priority |
|---|---|---|
| US-20 | As a developer, I want the agent to execute targeted tests so that it can identify implementation errors. | Must |
| US-21 | As a developer, I want the agent to revise its implementation when tests fail so that it can improve the proposed solution. | Must |
| US-22 | As a competition evaluator, I want patches applied to a fresh repository snapshot so that validation is independent of the agent's working environment. | Must |
| US-23 | As a competition evaluator, I want all required tests to pass so that only verified fixes receive credit. | Must |
| US-24 | As a developer, I want a record of test results and generated patches so that I can understand what the agent accomplished. | Should |

**Acceptance criteria**

- Targeted tests can be executed in the agent sandbox.
- The final patch is extracted.
- The verification environment starts from a clean repository snapshot.
- The patch is applied successfully.
- Required tests pass without failures, errors, or skips.
- A valid JUnit XML report is produced.

### Epic 6: Autonomous Operation and Resource Management

| ID | User story | Priority |
|---|---|---|
| US-25 | As a developer, I want the agent to operate without internet connectivity so that I can use it in offline environments. | Must |
| US-26 | As a competition evaluator, I want the agent to operate within time and tool-call limits so that all tasks are processed efficiently. | Must |
| US-27 | As a developer, I want the agent to manage its reasoning context so that long investigations do not exceed model limitations. | Must |
| US-28 | As an AI researcher, I want to use LoRA adapters so that specialized agent behavior can be developed without replacing the foundation model. | Should |
| US-29 | As a competition evaluator, I want all submitted agents to use an approved base model so that submissions comply with competition rules. | Must |

---

## 7. Functional Requirements

Functional requirements specify what the system must do. The requirements are grouped into 12 modules.

### FR-01: Task Intake and Processing

| ID | Functional requirement |
|---|---|
| FR-001 | The system shall accept a software engineering task containing a natural-language problem statement. |
| FR-002 | The system shall accept a repository identifier and the associated repository snapshot. |
| FR-003 | The system shall accept optional hints associated with the problem statement. |
| FR-004 | The system shall retrieve the task's base commit and repository context. |
| FR-005 | The system shall maintain task-specific execution state throughout the agent session. |
| FR-006 | The system shall process multiple benchmark tasks independently. |

### FR-02: Repository Exploration

| ID | Functional requirement |
|---|---|
| FR-007 | The system shall execute shell commands inside the designated repository workspace. |
| FR-008 | The system shall enumerate and inspect repository files. |
| FR-009 | The system shall read source files, including specified line ranges. |
| FR-010 | The system shall inspect repository metadata and Git status. |
| FR-011 | The system shall identify relevant modules, functions, classes, and symbols. |
| FR-012 | The system shall respect workspace boundaries when accessing files. |

### FR-03: Code Intelligence and Semantic Retrieval

| ID | Functional requirement |
|---|---|
| FR-013 | The system shall retrieve neighboring nodes for a specified code symbol. |
| FR-014 | The system shall support incoming and outgoing dependency relationships. |
| FR-015 | The system shall filter dependency relationships by edge type. |
| FR-016 | The system shall retrieve semantically similar code nodes using precomputed embeddings. |
| FR-017 | The system shall retrieve induced subgraphs connecting selected code symbols. |
| FR-018 | The system shall use code intelligence results to guide repository investigation. |

### FR-04: Reasoning and Root-Cause Analysis

| ID | Functional requirement |
|---|---|
| FR-019 | The system shall analyze the problem statement against the repository implementation. |
| FR-020 | The system shall identify potentially affected source files and code symbols. |
| FR-021 | The system shall formulate potential explanations for the reported issue. |
| FR-022 | The system shall evaluate proposed explanations using repository evidence. |
| FR-023 | The system shall select an implementation strategy consistent with existing repository conventions. |
| FR-024 | The system shall reconsider its proposed solution when test results or source-code evidence contradict its assumptions. |

### FR-05: Agent Orchestration

| ID | Functional requirement |
|---|---|
| FR-025 | The system shall support a root agent configured through `agent.yaml`. |
| FR-026 | The system shall support specialized subagents. |
| FR-027 | The system shall support sequential agent execution. |
| FR-028 | The system shall support parallel agent execution where appropriate. |
| FR-029 | The system shall support bounded iterative agent execution. |
| FR-030 | The system shall support specialized agent instructions and optional LoRA adapters. |
| FR-031 | The system shall support ADK skills with documented manifests and sandboxed scripts. |
| FR-032 | The system shall handle tool errors and allow recoverable execution to continue. |

### FR-06: Source-Code Editing

| ID | Functional requirement |
|---|---|
| FR-033 | The system shall modify existing non-empty source files. |
| FR-034 | The system shall create new source files when necessary. |
| FR-035 | The system shall create required parent directories for new files. |
| FR-036 | The system shall support exact source-code replacement. |
| FR-037 | The system shall support whitespace-tolerant source-code replacement. |
| FR-038 | The system shall detect ambiguous replacement operations. |
| FR-039 | The system shall prevent unauthorized filesystem path traversal. |
| FR-040 | The system shall avoid modifying protected test and test-runner configuration files. |

### FR-07: Testing and Debugging

| ID | Functional requirement |
|---|---|
| FR-041 | The system shall execute shell-based verification commands. |
| FR-042 | The system shall execute targeted pytest tests when testing is enabled. |
| FR-043 | The system shall inspect test output and error messages. |
| FR-044 | The system shall use test results to guide subsequent modifications. |
| FR-045 | The system shall support repeated investigation and repair within the available budget. |
| FR-046 | The system shall not claim successful verification when required tests have failed or have not been executed. |

### FR-08: Patch Generation and Submission

| ID | Functional requirement |
|---|---|
| FR-047 | The system shall generate a unified Git diff from the repository baseline. |
| FR-048 | The system shall include new source files in the generated patch. |
| FR-049 | The system shall exclude protected test and configuration modifications. |
| FR-050 | The system shall provide an explicit patch submission operation. |
| FR-051 | The system shall preserve patch information when the agent terminates without explicitly submitting, where supported by the harness. |
| FR-052 | The system shall produce a final completion response after its work is finished. |

### FR-09: Independent Patch Verification

| ID | Functional requirement |
|---|---|
| FR-053 | The evaluation system shall create a fresh verification sandbox. |
| FR-054 | The evaluation system shall restore the repository snapshot at the original base commit. |
| FR-055 | The evaluation system shall apply the generated agent patch. |
| FR-056 | The evaluation system shall restore protected test and configuration files before verification. |
| FR-057 | The evaluation system shall apply the benchmark's verification test patch. |
| FR-058 | The evaluation system shall execute the required pytest verification tests. |
| FR-059 | The evaluation system shall generate and validate JUnit XML test reports. |
| FR-060 | The evaluation system shall classify a task as resolved only when all required validation conditions are satisfied. |

### FR-10: Model and Fine-Tuning Management

| ID | Functional requirement |
|---|---|
| FR-061 | The system shall use one approved Gemma 4 base model per submission. |
| FR-062 | The system shall support the four permitted quantized model variants. |
| FR-063 | The system shall support optional PEFT LoRA adapters. |
| FR-064 | The system shall allow different adapters to be assigned to different agents using the same base model. |
| FR-065 | The system shall load generation configurations from approved configuration files. |
| FR-066 | The system shall enforce supported model and generation configuration constraints. |

### FR-11: Budget and Session Management

| ID | Functional requirement |
|---|---|
| FR-067 | The system shall track elapsed agent execution time. |
| FR-068 | The system shall track tool-call consumption. |
| FR-069 | The system shall enforce configured task execution limits. |
| FR-070 | The system shall provide current budget and patch status. |
| FR-071 | The system shall support context compaction to manage long-running sessions. |
| FR-072 | The system shall terminate or finalize work when applicable execution budgets are exhausted. |

### FR-12: Evaluation and Reporting

| ID | Functional requirement |
|---|---|
| FR-073 | The system shall generate one prediction for each benchmark task. |
| FR-074 | The system shall associate each prediction with its corresponding task identifier. |
| FR-075 | The system shall generate the required `submission.parquet` output through the evaluation pipeline. |
| FR-076 | The system shall record individual task results. |
| FR-077 | The system shall calculate the overall resolution rate. |
| FR-078 | The system shall retain available execution logs, patches, test outputs, and traces. |

---

## 8. Non-Functional Requirements

Non-functional requirements describe how well the system must operate, including performance, security, reliability, portability, and maintainability.

The following tables distinguish competition constraints from broader engineering expectations where possible.

### 8.1 Performance Requirements

| ID | Requirement | Target / constraint |
|---|---|---|
| NFR-001 | Task processing time | Complete all benchmark tasks within the competition's 12-hour submission execution limit. |
| NFR-002 | Agent execution time | Respect configured per-task time limits. |
| NFR-003 | Command execution | Maximum default command timeout of 300 seconds. |
| NFR-004 | Verification execution | Maximum verification timeout of 300 seconds. |
| NFR-005 | Tool output | Default output limit of 5,000 characters. |
| NFR-006 | File reading | Maximum 150 lines and 10,000 characters per `read_file` call. |
| NFR-007 | Context capacity | Respect the 32,768-token model context limit. |
| NFR-008 | Parallel processing | Support parallel agent execution and configurable benchmark concurrency. |

> **Time-budget distinction:** The 12-hour overall competition budget should not be confused with the per-task agent time budget. The harness README documents a default 60-minute agent session, which can be customized through evaluation configuration.

### 8.2 Reliability Requirements

| ID | Requirement | Description |
|---|---|---|
| NFR-009 | Patch correctness | Generated patches must resolve the underlying issue rather than merely change related code. |
| NFR-010 | Patch applicability | Generated patches must apply successfully to the original repository snapshot. |
| NFR-011 | Test reliability | Required verification tests must pass without failures, errors, or skips. |
| NFR-012 | Error recovery | The agent must handle recoverable tool errors without unnecessary termination. |
| NFR-013 | Session continuity | The system must preserve relevant task state during multi-turn reasoning. |
| NFR-014 | Reproducibility | The same task and base repository snapshot should support reproducible evaluation. |
| NFR-015 | Regression avoidance | The agent should minimize unintended changes to unrelated functionality. |
| NFR-016 | Completion integrity | The system must not report a patch as successfully resolved based solely on its own assertions. |

**Primary success metric: Resolution rate**

\[
\text{Resolution Rate} =
\frac{\text{Number of resolved tasks}}{\text{Total evaluated tasks}}
\times 100
\]

A task is resolved only when its patch applies and the independent verification process reports successful required tests.

### 8.3 Security Requirements

| ID | Requirement | Description |
|---|---|---|
| NFR-017 | Execution isolation | Repository commands must execute in the designated sandbox. |
| NFR-018 | Network isolation | Agent task execution must not require internet connectivity. |
| NFR-019 | Filesystem protection | The system must prevent path traversal outside authorized workspace directories. |
| NFR-020 | Submission security | Agent configurations must use declarative YAML rather than arbitrary Python entrypoints. |
| NFR-021 | Symlink protection | Submission paths must not escape the authorized submission directory through symlinks. |
| NFR-022 | Test integrity | The agent must not manipulate protected tests or test-runner configurations to obtain a passing result. |
| NFR-023 | Container isolation | Agent execution and independent verification must occur in separate environments. |

### 8.4 Resource and Hardware Requirements

| ID | Requirement | Competition constraint |
|---|---|---|
| NFR-024 | GPU availability | Evaluation infrastructure provides four NVIDIA L4 GPUs. |
| NFR-025 | GPU memory | 96 GB aggregate GPU memory. |
| NFR-026 | Model compatibility | Only the four specified quantized Gemma 4 variants are permitted. |
| NFR-027 | Container memory | 4 GiB RAM per sandbox container. |
| NFR-028 | Container CPU | Two vCPUs per sandbox container. |
| NFR-029 | Submission archive | Total unpacked archive must be less than 3 GiB. |
| NFR-030 | Adapter compatibility | LoRA adapters must use PEFT-compatible structures and `.safetensors` weights. |

> **Hardware distinction:** The competition's scoring infrastructure uses four L4 GPUs. The longer-term product vision of running on everyday consumer hardware requires a separate hardware-efficiency target and validation program. The competition does not establish a minimum consumer GPU or RAM specification.

### 8.5 Usability Requirements

| ID | Requirement | Description |
|---|---|---|
| NFR-031 | Understandable output | Final responses should clearly communicate task completion status. |
| NFR-032 | Action transparency | The system should make its investigation, edits, and verification results traceable. |
| NFR-033 | Consistent behavior | Agent instructions should provide predictable repository exploration and editing behavior. |
| NFR-034 | Developer reviewability | Generated patches should be readable, focused, and suitable for code review. |
| NFR-035 | Error clarity | Tool errors and test failures should provide actionable information. |

### 8.6 Maintainability and Extensibility

| ID | Requirement | Description |
|---|---|---|
| NFR-036 | Modular architecture | Separate issue analysis, repository exploration, reasoning, editing, and verification responsibilities. |
| NFR-037 | Extensible agents | Support adding specialized agents without replacing the entire architecture. |
| NFR-038 | Extensible skills | Support reusable repository-navigation and debugging skills. |
| NFR-039 | Model adaptability | Support approved LoRA adapter configurations. |
| NFR-040 | Configuration management | Support external prompts and sampling configurations using `!include`. |
| NFR-041 | Observability | Maintain task logs, execution traces, patch artifacts, and test reports. |
| NFR-042 | Reproducible deployment | Support packaging and deployment through the prescribed submission archive. |

---

## 9. Business Rules

Business rules define constraints that the system must always respect.

| ID | Business rule |
|---|---|
| BR-001 | Every agent in a submission must use the same approved base model. |
| BR-002 | Only the four specified quantized Gemma 4 models are permitted. |
| BR-003 | The submission must contain `agent.yaml` at the root of `submission.zip`. |
| BR-004 | All configuration references must resolve within the submission directory. |
| BR-005 | Arbitrary Python agent entrypoints are not permitted. |
| BR-006 | LoRA adapters must follow the required PEFT directory structure. |
| BR-007 | The agent must operate without internet access during repository task execution. |
| BR-008 | The agent must work within its assigned execution and tool-call budgets. |
| BR-009 | The agent must modify implementation code rather than protected tests to resolve an issue. |
| BR-010 | The generated patch must correspond to the original repository base commit. |
| BR-011 | The evaluation system must independently validate submitted patches. |
| BR-012 | A task receives a passing result only when the required tests pass and the JUnit report is valid. |
| BR-013 | The final submission must follow the required prediction output format. |

---

## 10. Dataset and Data Requirements

The competition provides a foundation for training, fine-tuning, and validating the agent.

### 10.1 Dataset inventory

| Dataset component | Quantity | Business / technical purpose |
|---|---:|---|
| Public development tasks | 129 | Agent development and validation |
| Repository snapshots | 129 | Reproducible repository environments |
| Graph files | 256 | Code structure and dependency exploration |
| Embedding archives | 256 | Semantic code retrieval |
| Precompiled dependency wheels | 124 | Offline package installation |
| Hidden evaluation tasks | Approximately 120 | Final performance evaluation |

### 10.2 Supported repositories

The public benchmark includes four repositories:

1. **FastAPI** — `fastapi/fastapi`
2. **Requests** — `psf/requests`
3. **Rich** — `Textualize/rich`
4. **HTTPX** — `encode/httpx`

### 10.3 Required data entities

The following entities provide a proposed data model for the system.

| Entity | Important attributes |
|---|---|
| `BenchmarkTask` | `instance_id`, `repo`, `base_commit`, `problem_statement`, `hints_text` |
| `Repository` | `repository_name`, `snapshot`, `base_commit` |
| `CodeNode` | `node_id`, `symbol_name`, `source_code` |
| `CodeEdge` | `source`, `target`, `relationship_type` |
| `CodeEmbedding` | `node_id`, `embedding_vector` |
| `AgentSession` | `session_id`, `task_id`, `status`, `elapsed_time` |
| `ToolExecution` | `tool_name`, `arguments`, `result`, `execution_status` |
| `CodeChange` | `filepath`, `original_content`, `modified_content` |
| `Patch` | `task_id`, `unified_diff`, `patch_status` |
| `TestExecution` | `test_name`, `exit_code`, `test_status` |
| `EvaluationResult` | `task_id`, `resolved`, `score`, `error` |

> **Training and evaluation boundary:** The reference patch and test patch in the published dataset are useful for local training and validation. They must not be treated as available information when solving hidden evaluation tasks.

---

## 11. End-to-End Workflow

The following process translates the requirements into an operational issue-to-patch workflow.

1. **Receive software issue**
   - Accept the issue description, repository identifier, and optional hints.

2. **Initialize repository sandbox**
   - Extract the correct snapshot, establish the base commit, and prepare offline dependencies.

3. **Understand the repository**
   - Inspect files, source code, graph nodes, dependencies, and semantic retrieval results.

4. **Investigate root cause**
   - Identify relevant components, formulate hypotheses, and select a repair strategy.

5. **Implement source-code fix**
   - Modify or create the necessary implementation files.

6. **Run targeted tests**
   - Inspect failures and refine the implementation when necessary.

7. **Generate and submit patch**
   - Create the unified Git diff and submit it through the harness.

8. **Perform independent verification**
   - Apply the patch in a fresh sandbox and execute the benchmark verification tests.

9. **Calculate evaluation result**
   - Classify the task as resolved or unresolved and record its result.

---

## 12. Performance Indicators

The most important performance indicator is the benchmark resolution rate. However, optimizing only this metric may encourage inefficient or overly complicated agent behavior.

The following additional KPIs are recommended for development and experimentation.

| KPI | Measurement | Business significance |
|---|---|---|
| Resolution rate | Passed tasks / total tasks | Primary competition performance |
| Patch applicability | Successfully applied patches / submitted patches | Measures patch quality |
| Test pass rate | Successful independent validations / submitted patches | Measures functional correctness |
| Tool efficiency | Average tool calls per task | Measures operational efficiency |
| Time per task | Average agent execution time | Measures productivity |
| Context efficiency | Tokens consumed per task | Measures reasoning efficiency |
| Regression rate | Patches introducing unrelated failures | Measures software reliability |
| Repository navigation efficiency | Relevant symbols discovered / exploration operations | Measures investigation effectiveness |
| Recovery rate | Recoverable errors followed by successful completion | Measures resilience |
| Hardware efficiency | Tasks resolved per unit of GPU resource | Measures deployment efficiency |

**Recommended primary KPI:** Maximize independent task resolution rate while minimizing time, tool calls, token consumption, and unnecessary source-code modifications.

---

## 13. Requirements Traceability

This matrix connects business objectives to user stories, functional requirements, and evaluation outcomes.

| Business objective | User stories | Functional requirements | Validation |
|---|---|---|---|
| Improve debugging productivity | US-01–US-04 | FR-001–FR-006, FR-019–FR-024 | Issue resolution |
| Improve repository understanding | US-05–US-09 | FR-007–FR-018 | Navigation accuracy |
| Enable autonomous reasoning | US-10–US-14 | FR-019–FR-032 | Successful multi-step investigation |
| Generate reliable patches | US-15–US-19 | FR-033–FR-040, FR-047–FR-052 | Patch applicability |
| Verify software fixes | US-20–US-24 | FR-041–FR-060 | Independent pytest results |
| Support offline operation | US-25 | FR-007, FR-041 | No internet dependency |
| Optimize execution resources | US-26–US-27 | FR-067–FR-072 | Budget compliance |
| Support model specialization | US-28–US-29 | FR-061–FR-066 | Model and adapter validation |

---

## 14. Risks and Mitigations

| Risk | Probability | Impact | Recommended mitigation |
|---|---|---|---|
| Model fails to understand complex repositories | High | High | Fine-tune on repository exploration and software engineering trajectories |
| Incorrect root-cause identification | High | High | Evidence-based investigation and specialized analysis agents |
| Excessive tool usage | High | High | Budget-aware planning and targeted retrieval |
| Context-window exhaustion | Medium | High | Context compaction and read-only analyzer subagents |
| Incorrect source modifications | High | High | Incremental editing and targeted tests |
| Patch fails to apply | Medium | High | Generate minimal, baseline-compatible unified diffs |
| Test manipulation or accidental test modifications | Medium | High | Protected-file restrictions and independent verification |
| Model performance degrades after fine-tuning | Medium | High | Maintain validation datasets and compare against the base model |
| Poor performance on unseen repositories | High | High | Cross-repository evaluation and generalization testing |
| Consumer hardware limitations | High | High | Quantization, LoRA optimization, and smaller-model experiments |

---

## 15. Recommended Development Priorities

Given the competition's limited remaining time, implementation should be prioritized according to its direct contribution to the final resolution rate.

### Priority 1 — Core agent

**Critical**

- Root agent configuration.
- Strong software engineering system prompt.
- Repository exploration.
- Source-code editing.
- Correct patch generation.

### Priority 2 — Repository intelligence

**Critical**

- Graph-based navigation.
- Semantic code retrieval.
- Dependency analysis.
- Read-only code analyzer subagent.

### Priority 3 — Reliability

**Critical**

- Targeted test execution.
- Error recovery.
- Patch verification.
- Budget-aware operation.

### Priority 4 — Model post-training

**High**

- Software engineering instruction tuning.
- Repository navigation trajectories.
- Tool-use training.
- LoRA experimentation.

### Priority 5 — Advanced optimization

**Enhancement**

- Reinforcement learning.
- Adaptive agent delegation.
- Hardware optimization.
- Cross-repository generalization.

> **Implementation recommendation:** Do not spend most of the remaining development time implementing a sophisticated multi-agent architecture before establishing that a single agent can consistently solve benchmark tasks. Build a reliable baseline, measure it, and introduce specialized agents where experiments demonstrate an improvement.

---

## 16. Product Definition

# Gemma 4 Autonomous Developer Agent

| Attribute | Definition |
|---|---|
| Product category | Offline autonomous AI software engineering system |
| Primary users | Software developers, open-source maintainers, and software engineering teams |
| Core capability | Autonomous issue-to-patch resolution |
| Technology foundation | Post-trained Gemma 4, LoRA adapters, agent orchestration, repository code graphs, semantic retrieval, and sandboxed execution |
| Primary deliverable | A valid unified Git patch that passes independent software tests |
| Primary success metric | Independent benchmark resolution rate |

### Value proposition

Enable developers to delegate complex software debugging and implementation tasks to an autonomous AI agent that can understand codebases, investigate problems, propose fixes, and verify its work without relying on cloud-based coding services.

---

## 17. Strategic Innovation and Research Direction

From a business and systems-analysis perspective, the strongest opportunity is not simply to fine-tune Gemma 4 to generate better Python code.

It is to develop a **repository-aware, evidence-driven autonomous software engineering architecture**.

### 17.1 Four interconnected capabilities

1. **Structural intelligence:** Use code graphs to understand relationships between functions, classes, and modules.
2. **Semantic intelligence:** Use embeddings to retrieve relevant code without exhaustively reading entire repositories.
3. **Procedural intelligence:** Train the model to execute structured software engineering workflows, including investigation, implementation, and verification.
4. **Verification-driven intelligence:** Use actual test outcomes as feedback for subsequent decisions rather than relying on the model's confidence.

The combination creates a stronger proposition than code generation alone.

### 17.2 Suggested central research question

*How can graph-enhanced repository understanding, semantic code retrieval, and verification-driven post-training improve the autonomous software engineering capabilities of resource-constrained open language models on complex, multi-step software maintenance tasks?*

This question provides a scientific foundation for investigating whether specialized post-training and repository intelligence can improve the ability of smaller models to solve real-world software engineering problems.

---

## Conclusion

The proposed Gemma 4 Autonomous Developer Agent is intended to move beyond code completion toward autonomous, evidence-driven software maintenance. Its success depends on the integration of repository understanding, structured reasoning, controlled code modification, and independent verification.

The central engineering objective is to produce **small, applicable, and correct patches** under the competition's model, execution, security, and resource constraints. The central research opportunity is to determine how structural and semantic repository intelligence, combined with verification-driven post-training, can improve the performance and generalization of resource-constrained open language models.
