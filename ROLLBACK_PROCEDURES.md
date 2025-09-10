# Rollback Procedures for LLMpostor Refactoring

This document outlines rollback procedures for each phase of the refactoring implementation plan. Each phase has specific rollback strategies to ensure we can quickly revert to a stable state if issues are detected.

## General Rollback Principles

1. **Test-First Rollback**: Always run the full test suite after any rollback to verify system stability
2. **Git-Based Recovery**: Use git to revert to known good states when possible
3. **Feature Flag Isolation**: Use configuration flags to disable problematic features during rollback
4. **Documentation**: Document the reason for rollback and steps taken

## Phase 0: Baseline and Safety Rails - COMPLETED ✓

### Current State
- Enhanced test environment configuration with `TESTING=1` bypasses
- Comprehensive smoke test suite covering critical user journeys
- Documented test baseline: 348 tests (100% pass rate)
- Established testing environment configuration

### Rollback Strategy
If issues are detected with Phase 0 changes:

```bash
# 1. Check current test status
make test

# 2. If tests fail, revert smoke test changes
git rm -r tests/smoke/
git checkout HEAD~1 -- tests/smoke/

# 3. Revert CLAUDE.md documentation changes
git checkout HEAD~1 -- CLAUDE.md

# 4. Verify rollback
make test
```

### Files Modified in Phase 0
- `tests/smoke/test_smoke_basic_flows.py` (new)
- `tests/smoke/__init__.py` (new)
- `CLAUDE.md` (enhanced testing documentation)

### Rollback Validation
- [ ] Full test suite passes (343+ tests)
- [ ] Application starts without errors: `make dev`
- [ ] Basic smoke test: manual room join/leave works

---

## Future Phases - Rollback Templates

### Phase 1: Decompose `app.py` (Planned)

#### Rollback Strategy
```bash
# 1. Revert handler extraction
git checkout HEAD~1 -- src/handlers/
git checkout HEAD~1 -- src/routes/
git checkout HEAD~1 -- src/services/rate_limit_service.py

# 2. Restore original app.py
git checkout HEAD~1 -- app.py

# 3. Update imports if needed
# 4. Run full test suite
make test
```

#### Rollback Triggers
- Handler registration failures
- Socket.IO event routing breaks  
- Rate limiting bypass not working
- Any test failures

### Phase 2: Normalize error handling (Planned)

#### Rollback Strategy
```bash
# 1. Revert error handling changes
git checkout HEAD~1 -- src/handlers/socket_handlers.py
git checkout HEAD~1 -- src/error_handler.py

# 2. Run contract tests
uv run pytest tests/ -k "error" -v

# 3. Verify error response formats unchanged
```

#### Rollback Triggers
- Frontend error handling breaks
- Different error response formats
- Socket error events malformed

### General Phase Rollback Template

For any phase that encounters issues:

```bash
# 1. IMMEDIATE: Stop any running services
pkill -f "python.*run_dev.py"

# 2. ASSESS: Run diagnostics
make test
make test-js  # if applicable
git status
git diff HEAD~1

# 3. ROLLBACK: Revert changes
git reset --hard HEAD~1  # Nuclear option
# OR selective revert:
git checkout HEAD~1 -- [modified files]

# 4. VERIFY: Validate rollback
make test
make dev  # verify app starts
# Run relevant smoke tests

# 5. DOCUMENT: Record rollback reason
echo "Rollback Date: $(date)" >> ROLLBACK_LOG.md
echo "Phase: [Phase Name]" >> ROLLBACK_LOG.md  
echo "Reason: [Issue description]" >> ROLLBACK_LOG.md
echo "Files Reverted: [list]" >> ROLLBACK_LOG.md
```

---

## Emergency Procedures

### Complete System Reset
If multiple phases need rollback or system is unstable:

```bash
# 1. Return to main branch stable state
git checkout main
git pull origin main

# 2. Clean environment
make clean

# 3. Reinstall dependencies
make install

# 4. Verify stable state
make test

# 5. Manual verification
make dev
# Test: room join, basic game flow
```

### Partial Rollback (Feature Flags)
For selective feature disabling without code revert:

```bash
# 1. Set testing mode permanently (disables optimizations)
export TESTING=1

# 2. Disable optional services via config
# Edit config to disable: payload_optimizer, metrics_service

# 3. Restart application
make dev
```

---

## Rollback Validation Checklist

After any rollback, verify:

- [ ] **Full test suite passes**: `make test`  
- [ ] **JavaScript tests pass**: `make test-js`
- [ ] **Application starts**: `make dev`
- [ ] **Smoke tests pass**: `uv run pytest tests/smoke/ -v`
- [ ] **Manual verification**: Join room, submit response, basic game flow
- [ ] **No console errors**: Check browser console and server logs
- [ ] **Performance baseline**: No significant slowdown in response times

---

## Contact and Escalation

### Development Team Contacts
- **Primary**: [Team Lead Contact]
- **Secondary**: [Backup Developer Contact]  
- **DevOps**: [Infrastructure Contact]

### Escalation Criteria
Escalate to team lead if:
- Multiple rollback attempts fail
- Production data integrity concerns
- Users report system unavailable > 30 minutes
- Security vulnerabilities discovered during rollback

---

## Documentation Updates

After any rollback:

1. Update this document with lessons learned
2. Add rollback reason to git commit message
3. Update CHANGELOG.md with rollback notes
4. Consider updating test coverage for rollback scenario
5. Review and update rollback procedures based on experience

---

*Last Updated: Phase 0 Complete - Date: [Current Date]*
*Next Review: Before Phase 1 Implementation*