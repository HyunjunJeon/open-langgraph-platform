# Documentation Guide — Open LangGraph Platform

This document explains what lives in the `docs/` directory and how to navigate it.

---

## Overview

The `docs/` folder contains the project’s technical documentation and guides for developers, contributors, and operators.

### What `docs/` is for
- Learning: onboarding guides for new developers
- Reference: quick lookups for daily work
- Architecture: system design and structure
- Troubleshooting: common issues and fixes
- Examples: concrete scenarios and code walkthroughs

---

## Document Index

### Core Documents

| Document | Purpose | Audience |
|---------|---------|----------|
| [README.md](README.md) | Docs hub and starting point | Everyone |
| [developer-guide.md](developer-guide.md) | Dev environment and workflow (English) | Developers |
| [developer-guide-ko.md](developer-guide-ko.md) | Dev environment and workflow (Korean) | Developers |
| [api-reference.md](api-reference.md) | API reference entry point (English) | Everyone |
| [api-reference-ko.md](api-reference-ko.md) | API reference entry point (Korean) | Everyone |

### Architecture & Design

| Document | Purpose | Audience |
|---------|---------|----------|
| [architecture.md](architecture.md) | System architecture (English) | Developers, architects |
| [architecture-ko.md](architecture-ko.md) | System architecture (Korean) | Developers, architects |

### Development Tools & Quality

| Document | Purpose | Audience |
|---------|---------|----------|
| [code-quality.md](code-quality.md) | Code quality standards and tools (English) | Contributors, developers |
| [code-quality-ko.md](code-quality-ko.md) | Code quality standards and tools (Korean) | Contributors, developers |
| [migration-cheatsheet.md](migration-cheatsheet.md) | DB migration quick reference (English) | Developers |
| [migration-cheatsheet-ko.md](migration-cheatsheet-ko.md) | DB migration quick reference (Korean) | Developers |

### Observability & Monitoring

| Document | Purpose | Audience |
|---------|---------|----------|
| [langfuse-usage.md](langfuse-usage.md) | Langfuse tracing/observability setup (English) | Developers, DevOps |
| [langfuse-usage-ko.md](langfuse-usage-ko.md) | Langfuse tracing/observability setup (Korean) | Developers, DevOps |

### Security & Operations

| Document | Purpose | Audience |
|---------|---------|----------|
| [audit-logging.md](audit-logging.md) | Audit logging design/operations guide (English) | Security, DevOps, developers |
| [rate-limiting.md](rate-limiting.md) | Rate limiting configuration/behavior (English) | DevOps, developers |

### Troubleshooting & Examples

| Document | Purpose | Audience |
|---------|---------|----------|
| [troubleshooting-ko.md](troubleshooting-ko.md) | Troubleshooting guide (Korean only for now) | Developers |
| [examples-ko.md](examples-ko.md) | Practical examples/scenarios (Korean only for now) | Developers, users |

---

## Recommended Reading Paths

### New developers

```
1. README.md
   ↓
2. developer-guide.md (or developer-guide-ko.md)
   ↓
3. code-quality.md (or code-quality-ko.md)
   ↓
4. migration-cheatsheet.md (or migration-cheatsheet-ko.md)
   ↓
5. examples-ko.md (Korean only for now)
```

Goal: set up the environment quickly and make your first API call.

### Architecture deep dive

```
1. architecture.md (or architecture-ko.md)
   ↓
2. developer-guide.md (or developer-guide-ko.md)
   ↓
3. examples-ko.md (Korean only for now)
```

Goal: understand the integration pattern between LangGraph and FastAPI.

### Contributors

```
1. code-quality.md (or code-quality-ko.md)
   ↓
2. developer-guide.md (or developer-guide-ko.md)
   ↓
3. migration-cheatsheet.md (or migration-cheatsheet-ko.md)
   ↓
4. ../CONTRIBUTING.md
```

Goal: meet all quality standards before opening a PR.

### Production deployment

```
1. developer-guide.md (deployment sections)
   ↓
2. langfuse-usage.md (or langfuse-usage-ko.md)
   ↓
3. troubleshooting-ko.md (Korean only for now)
   ↓
4. migration-cheatsheet.md (or migration-cheatsheet-ko.md)
```

Goal: deploy safely with monitoring and a migration strategy.

### Daily work (quick links)
- Migration quick reference: `migration-cheatsheet.md` / `migration-cheatsheet-ko.md`
- Troubleshooting: `troubleshooting-ko.md`
- Before code review: `code-quality.md` / `code-quality-ko.md`
- Implementing new features: `examples-ko.md`

---

## Korean/English Mapping

For major documents, the project provides both Korean and English versions.

| Korean | English | Notes |
|--------|---------|-------|
| [developer-guide-ko.md](developer-guide-ko.md) | [developer-guide.md](developer-guide.md) | Developer guide |
| [code-quality-ko.md](code-quality-ko.md) | [code-quality.md](code-quality.md) | Code quality |
| [migration-cheatsheet-ko.md](migration-cheatsheet-ko.md) | [migration-cheatsheet.md](migration-cheatsheet.md) | Migration cheat sheet |
| [langfuse-usage-ko.md](langfuse-usage-ko.md) | [langfuse-usage.md](langfuse-usage.md) | Langfuse usage |

Korean-only (for now):
- [architecture-ko.md](architecture-ko.md) has an English version: [architecture.md](architecture.md)
- [troubleshooting-ko.md](troubleshooting-ko.md)
- [examples-ko.md](examples-ko.md)

Language selection:
- Prefer the English version when available (no `-ko` in the filename).
- Use `-ko.md` when you need the Korean version.

---

## Document Templates

### General guide template

```markdown
# [Title]

[Short intro: what this document covers]

## Contents
- [Section 1](#section-1)
- [Section 2](#section-2)

---

## Section 1

[Content]

### Subsection

[Details]

~~~bash
# Code example
~~~

## Section 2

[Content]

---

## References
- [Related document]
- [External resource]
```

### Troubleshooting template

```markdown
# [Issue Title]

**Symptoms**
~~~text
[Error message or symptom description]
~~~

**Root cause**
- Cause 1
- Cause 2

**Fix**
1. First fix
   ~~~bash
   # Command example
   ~~~

2. Second fix
   ~~~bash
   # Command example
   ~~~

**Verify**
~~~bash
# Verification command
~~~
```

---

## Additional Resources

### Project docs
- [Main README](../README.md) — project overview
- [Root `AGENTS.md`](../AGENTS.md) — agent router and always-on principles
- [Structure guide](structure-guide.md) — (Reference) full structure/component map
- [CLAUDE.md](../CLAUDE.md) — design/patterns/extra context

### External docs
- [LangGraph documentation](https://langchain-ai.github.io/langgraph/)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Alembic documentation](https://alembic.sqlalchemy.org/)
- [Agent Protocol spec](https://github.com/langchain-ai/agent-protocol)
