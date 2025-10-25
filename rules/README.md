# Cursor Rules Organization

This directory contains organized rule files that guide the AI assistant's behavior for different aspects of the project.

## Rule Files Overview

### Critical Priority Rules (Always Applied)
- **`generic-rules-only.mdc`** - All rules must be portable and project-agnostic
- **`test-quality-requirements.mdc`** - All tests must pass without exception
- **`tests-location.mdc`** - Behavior-driven testing standards and file organization
- **`no-emojis.mdc`** - Prohibits emoji usage throughout the project
- **`incremental-collaboration.mdc`** - Prevents reversing established work during sessions
- **`security-privacy.mdc`** - Security and data privacy protection standards
- **`destructive-ops-safety.mdc`** - Ironclad safeguards for destructive operations
- **`env-var-safety.mdc`** - Mandatory scoping and cleanup of environment variables

### High Priority Rules
- **`composition-container.mdc`** - Centralized composition root and dependency injection
- **`oop-solid.mdc`** - Object-oriented programming and SOLID principles with mandatory checkpoints
- **`mypy-type-safety.mdc`** - Type safety and static analysis requirements
- **`performance-optimization.mdc`** - Performance standards for resource-intensive operations
- **`configuration-management.mdc`** - Centralized and validated configuration management
- **`error-handling-logging.mdc`** - Comprehensive error handling and structured logging (UI/log separation)
- **`data-validation.mdc`** - Input validation and schema compliance standards
- **`monitoring-observability.mdc`** - Monitoring, metrics, and health checks
- **`windows-shell.mdc`** - Windows PowerShell command guidelines and restrictions
- **`git-commit-guidance.mdc`** - Version control best practices

### Medium Priority Rules
- **`test-coverage-standards.mdc`** - 80% minimum test coverage per module requirement
- **`dead-code-detection.mdc`** - Systematic identification and safe removal of unused code
- **`documentation-standards.mdc`** - Comprehensive documentation and code comment standards
- **`documentation-updates.mdc`** - Documentation maintenance requirements
- **`dependency-management.mdc`** - Secure and maintainable dependency handling

## Rule Targeting Strategy

### File Pattern Targeting
- **Python application code**: `**/*.py` (excluding `tests/`), typically governed by:
  - `composition-container.mdc`, `oop-solid.mdc`, `dead-code-detection.mdc`, `security-privacy.mdc`
  - `performance-optimization.mdc`, `error-handling-logging.mdc`, `data-validation.mdc`, `monitoring-observability.mdc`, `mypy-type-safety.mdc`
- **Configuration files**: `configuration-management.mdc` applies to `*.toml`, `*.yaml`, `*.json`
- **Documentation**: `documentation-standards.mdc` applies to `**/*.md` and code comment sections
- **Dependencies**: `dependency-management.mdc` applies to `pyproject.toml` and `requirements*.txt`
- **Test code**: `tests/**/*.py` and `**/*test*.py`:
  - `test-quality-requirements.mdc`, `test-coverage-standards.mdc`, `tests-location.mdc`, `env-var-safety.mdc`
- **All files**: `git-commit-guidance.mdc`, `windows-shell.mdc`, and `generic-rules-only.mdc` apply globally

### Priority Levels
- **Critical**: Core project standards that must never be violated
- **High**: Important architectural and platform-specific requirements  
- **Medium**: Best practices that improve code quality and maintainability

## Frontmatter Configuration

Each rule file uses YAML frontmatter to specify:

```yaml
---
appliesTo: ["file/pattern/**/*.ext"]  # File targeting
alwaysApply: true                     # Apply regardless of context
priority: critical|high|medium        # Rule importance
context: ["terminal", "commands"]     # Context-specific application
---
```

## Rule Effectiveness

This multi-file approach provides:

1. **Contextual Relevance** - Rules apply only where appropriate
2. **Reduced Token Usage** - Only relevant rules are loaded
3. **Better Organization** - Clear separation of concerns
4. **Team Collaboration** - Parallel development without conflicts
5. **Maintainability** - Easy to update specific rule categories

## Adding New Rules

When adding new rules:

1. Create a descriptive filename: `feature-specific-rules.mdc`
2. Add appropriate frontmatter for targeting and priority
3. Use clear, actionable language
4. Include examples of correct and incorrect usage
5. Update this README to document the new rule

## Rule Interaction

Rules are processed based on:
- **Priority**: Critical > High > Medium
- **Context**: More specific rules take precedence
- **File Matching**: Rules only apply to targeted file patterns

This ensures consistent, efficient, and contextually appropriate AI assistance throughout the project.

## Enforcement Hooks Examples

- **Environment safety**: Autouse pytest fixture snapshots and restores `os.environ`, failing tests on leaks; CI snapshots env at job start/end and fails on diffs.
- **Destructive ops**: Commands refuse execution without an env opt-in and `--force`; display counts and confirmations; log warnings before and results after.
- **Centralized logging**: All modules obtain a logger via a centralized setup; UI output is not duplicated in logs; optional JSON logs via env toggle.
- **Composition root**: CLI/orchestrators obtain dependencies via a small container; no direct instantiation of infrastructure inside business logic.
