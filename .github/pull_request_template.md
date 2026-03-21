## Summary

<!-- Brief description of the changes -->

## Changes

-

## Type of Change

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Refactoring (no functional changes)
- [ ] Documentation update
- [ ] Test improvement

## Code Quality Checklist

- [ ] `ruff check src/ tests/` passes with zero warnings (run on ENTIRE project, not just changed files)
- [ ] `ruff format src/ tests/` applied (ENTIRE project)
- [ ] `mypy src/piea/ --strict` passes with zero errors
- [ ] Tests pass and coverage meets current threshold (`pytest tests/ -v`)
- [ ] New code has type annotations (use `dict[str, Any]` for external JSON dicts, not `dict[str, object]`)
- [ ] Functions/classes have docstrings
- [ ] If API endpoint: documented in OpenAPI schema
- [ ] FastAPI `Depends()` providers for closeable resources use async generator with `finally: await x.close()`

## Security Checklist (SECURITY_WORKFLOW.md Section 3.3)

- [ ] No real API keys, tokens, or passwords in the diff
- [ ] No real email addresses, names, or IP addresses in source code or test data
- [ ] Test fixtures use synthetic data only (`@example.com`, `192.0.2.x`, etc.)
- [ ] Error messages do not expose PII (field values, emails, IPs)
- [ ] Log statements do not include raw PII (use hashed or redacted forms)
- [ ] New environment variables are documented in `.env.example` (empty values only)
- [ ] No `.env`, `.pem`, `.key`, or credential files in the diff

## Test Plan

<!-- How was this tested? -->

## Related Issues

<!-- Link any related issues: Fixes #123, Related to #456 -->
