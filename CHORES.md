# Chores & Small Tasks

This document tracks small maintenance tasks, refactoring, and technical debt. For major features and roadmap items, see `docs/IMPLEMENTATION_ROADMAP.md`.

## Code Quality

- [ ] Add type hints to any remaining untyped functions
- [ ] Run mypy and fix any type checking warnings
- [ ] Add docstrings to any undocumented public methods
- [ ] Review and update outdated comments

## Testing

- [ ] Improve test coverage for edge cases
- [ ] Add integration tests for cross-component workflows
- [ ] Review and remove any skipped/disabled tests
- [ ] Update test fixtures to use realistic data

## Documentation

- [ ] Review all docstrings for accuracy
- [ ] Update code examples in docs to match current API
- [ ] Fix any broken internal doc links
- [ ] Add missing configuration examples

## Technical Debt

- [ ] Review TODOs and FIXMEs in codebase
- [ ] Refactor any duplicated code
- [ ] Update deprecated dependencies
- [ ] Clean up unused imports and dead code

## Configuration & Setup

- [ ] Validate all environment variables are documented
- [ ] Ensure example configs are up to date
- [ ] Test setup instructions on fresh environment
- [ ] Review .gitignore for completeness

## Performance

- [ ] Profile slow operations and optimize
- [ ] Review database query efficiency
- [ ] Check for memory leaks in long-running processes
- [ ] Optimize large file operations

## Security

- [ ] Review authentication mechanisms
- [ ] Check for exposed secrets or tokens
- [ ] Validate input sanitization
- [ ] Update security-related dependencies

## Agentic IDE Optimization

Following best practices from [agentic-ide-power-user](https://github.com/reubenjohn/agentic-ide-power-user):

- [ ] Split CLAUDE.md into modular referenced files (currently 705 lines/28KB - approaching context rot threshold)
- [ ] Create pull request template following agentic IDE best practices
- [ ] Remove redundant documentation through cross-referencing
- [ ] Create .prompt.md files for common workflows (e.g., phase implementation, testing)
- [ ] Add file-pattern-specific instructions for better context targeting
- [ ] Implement progressive disclosure in documentation (instructions → rules → prompts hierarchy)
- [ ] Review and optimize Signal-to-Noise Ratio across all context files

## Cleanup

- [ ] Remove obsolete demo scripts or mark as archived
- [ ] Delete unused configuration files
- [ ] Clean up temporary or test files
- [ ] Archive completed phase validation files
- [ ] Remove or consolidate PHASE4_*.md files from repo root (move to appropriate location in docs/ or delete)

---

**How to use this file:**
1. Add new items as you discover them during development
2. Check off items as you complete them
3. Remove completed items periodically (monthly cleanup)
4. Keep it focused on small, concrete tasks (< 2 hours each)
