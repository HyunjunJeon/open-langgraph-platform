# 🚀 Quick Reference: Code Quality Management

## Guide for New Contributors

### One-Time Setup (2 minutes)

```bash
# 1. Clone the repository
git clone https://github.com/HyunjunJeon/open-langgraph-platform.git
cd opensource-langgraph-platform

# 2. Install dependencies and hooks
make dev-install

# Or if you don't use Make:
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

### Daily Workflow

```bash
# 1. Create a branch
git checkout -b feat/my-feature

# 2. Make your changes
# ... edit files ...

# 3. Before committing (optional but recommended)
make format    # Auto-fix formatting
make test      # Run tests

# 4. Commit (hooks will run automatically!)
git add .
git commit -m "feat: add my feature"

# 5. Push and create a PR
git push origin feat/my-feature
```

---

## Commit Message Format

**Required Format:** `type(scope): description`

### Quick Examples

```bash
✅ Good Examples:
git commit -m "feat: add user authentication"
git commit -m "fix(api): resolve rate limiting bug"
git commit -m "docs: update installation guide"
git commit -m "test: add e2e tests for threads"
git commit -m "chore: upgrade dependencies"

❌ Bad Examples:
git commit -m "fixed stuff"
git commit -m "WIP"
git commit -m "Update"
git commit -m "changes"
```

### Types

| Type | When to Use | Example |
|------|-------------|---------|
| `feat` | New feature | `feat: add OAuth login` |
| `fix` | Bug fix | `fix: resolve memory leak` |
| `docs` | Documentation | `docs: update API guide` |
| `style` | Formatting | `style: fix indentation` |
| `refactor` | Code refactoring | `refactor: simplify auth logic` |
| `perf` | Performance | `perf: optimize database queries` |
| `test` | Tests | `test: add unit tests for auth` |
| `chore` | Maintenance | `chore: update dependencies` |
| `ci` | CI/CD | `ci: add coverage reporting` |

### Scope (Optional)

Used to specify the affected part:
- `api`, `auth`, `db`, `graph`, `tests`, `docs`, `ci`

---

## What Happens When You Commit?

```
git commit -m "feat: add feature"
         ↓
    Git hooks run automatically
         ↓
┌────────────────────────────┐
│ 1. Ruff Format             │ ← Code formatting
│ 2. Ruff Lint               │ ← Quality check
│ 3. mypy Type Check         │ ← Type validation
│ 4. Bandit Security         │ ← Security issue scan
│ 5. File Checks             │ ← File validation
│ 6. Commit Message Check    │ ← Format validation
└────────────────────────────┘
         ↓
    All pass? ✅
         ↓
   Commit successful!
```

---

## Common Issues & Quick Fixes

### ❌ "Invalid commit message format"

**Error:**
```
❌ Commit message must follow format: type(scope): description
```

**Solution:**
```bash
# Use the correct format
git commit -m "feat: add new feature"
```

### ❌ "Ruff formatting failed"

**Error:**
```
❌ Files would be reformatted
```

**Solution:**
```bash
# Auto-fix formatting
make format

# Stage the changes
git add .

# Commit again
git commit -m "feat: add feature"
```

### ❌ "Linting errors found"

**Error:**
```
❌ Found 5 linting errors
```

**Solution:**
```bash
# See what's wrong
make lint

# Auto-fix what's possible
make format

# Manually fix the rest
# Then commit again
```

### ❌ "Type check failed"

**Error:**
```
❌ mypy found type errors
```

**Solution:**
```bash
# Check the specific errors
make type-check

# Add type hints
def my_function(name: str) -> str:
    return f"Hello {name}"
```

---

## Emergency: Bypassing Hooks

**⚠️ Not recommended** - will still fail in CI!

```bash
git commit --no-verify -m "emergency fix"
```

Use only in a true emergency. Your PR will still need to pass CI.

---

## Before Pushing: Run All Checks

```bash
# Run everything that CI will run
make ci-check
```

This runs:
- ✅ Formatting
- ✅ Linting
- ✅ Type checking
- ✅ Security scan
- ✅ Tests

---

## Pull Request Checklist

Before creating a PR:

- [ ] Git hooks installed (`make setup-hooks`)
- [ ] All commits follow the format
- [ ] Tests pass (`make test`)
- [ ] Code is formatted (`make format`)
- [ ] No linting errors (`make lint`)
- [ ] PR title follows the format: `type: description`

---

## Available Commands

```bash
make help          # Show all commands
make dev-install   # Install dependencies
make setup-hooks   # Install git hooks
make format        # Format code
make lint          # Check code quality
make type-check    # Type check
make security      # Security scan
make test          # Run tests
make test-cov      # Run tests with coverage
make ci-check      # Run all CI checks
make clean         # Clean up cache files
```

---

## CI/CD Pipeline

Every push and PR triggers:

1. **Formatting Check** - Code must be formatted
2. **Lint Check** - No quality issues
3. **Type Check** - Types must be valid
4. **Security Check** - No vulnerabilities
5. **Tests** - All tests must pass
6. **Coverage** - Generate coverage report

**Matrix:** Tests run on Python 3.11 and 3.12

---

## Branch Protection (Admins)

On GitHub, enable the following for the `main` branch:

- ✅ Require status checks to pass before merging
- ✅ Require PR review (1 approval)
- ✅ Require branches to be up to date
- ✅ Require conversation resolution

---

## Getting Help

1. **Read the error message** - It tells you what to fix
2. **Check ENFORCEMENT.md** - Detailed troubleshooting
3. **Run `make ci-check`** - Test everything locally
4. **Ask in a PR comment** - Admins will help

---

## Why This Matters

### For You
- ✅ Catch bugs before review
- ✅ Learn best practices
- ✅ Faster PR approvals

### For the Team
- ✅ Consistent code style
- ✅ Higher quality
- ✅ Less review time
- ✅ Better maintainability

---

## Quick Start Checklist

- [ ] Repository cloned
- [ ] `make dev-install` complete
- [ ] `make setup-hooks` complete ← **Important**
- [ ] Test commit successful
- [ ] Read CONTRIBUTING.md
- [ ] Ready to contribute! 🚀

---

**Remember:** The tools are here to help! They catch issues early so you can focus on writing great code. 💪
