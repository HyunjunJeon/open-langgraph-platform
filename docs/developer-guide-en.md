# Open LangGraph Developer Guide

Welcome to Open LangGraph! This guide helps everyone from developers new to database migrations to seasoned experts get started with development.

## 📋 Table of Contents

- [🚀 Quick Start for New Developers](#-quick-start-for-new-developers)
- [✨ Code Quality and Standards](#-code-quality-and-standards)
- [📚 Understanding Database Migrations](#-understanding-database-migrations)
- [🔧 Database Migration Commands](#-database-migration-commands)
- [🛠️ Development Workflow](#️-development-workflow)
- [📁 Project Structure](#-project-structure)
- [🔍 Understanding Migration Files](#-understanding-migration-files)
- [🚨 Common Issues and Solutions](#-common-issues-and-solutions)
- [🧪 Testing Your Changes](#-testing-your-changes)
- [🚀 Production Deployment](#-production-deployment)
- [📖 Best Practices](#-best-practices)
- [🔗 Useful Resources](#-useful-resources)
- [🆘 Getting Help](#-getting-help)
- [📋 Quick Reference](#-quick-reference)

## 🚀 Quick Start for New Developers

### Prerequisites

- Python 3.11+
- Docker
- Git
- uv (Python package manager)

### Initial Setup (5 minutes)

```bash
# 1. Clone and set up
git clone https://github.com/HyunjunJeon/open-langgraph-platform.git
cd open-langgraph
uv install

# 2. Activate virtual environment (Important!)
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows

# 3. Start everything (Database + Migrations + Server)
docker compose up open-langgraph
```

🎉 **Ready to develop!** Check out the API at http://localhost:8000/docs.

## ✨ Code Quality and Standards

Open LangGraph uses automated code quality checks to maintain high standards and consistency.

### Setup

**Option 1: Use Make (Recommended - automatically installs hooks)**
```bash
make dev-install     # Install dependencies + git hooks
```

**Option 2: Use uv directly**
```bash
uv sync
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

Hooks automatically check your code before you commit.

### What's Checked Automatically

The following checks run automatically on commit:
- ✅ **Code Formatting** (Ruff) - Automatically formats code
- ✅ **Linting** (Ruff) - Checks code quality
- ✅ **Type Checking** (mypy) - Verifies type hints
- ✅ **Security Scanning** (Bandit) - Scans for vulnerabilities
- ✅ **Commit Messages** - Enforces format

### Commit Message Format

**Required format:** `type(scope): description`

```bash
# Good examples ✅
git commit -m "feat: add user authentication"
git commit -m "fix(api): resolve rate limiting bug"
git commit -m "docs: update installation guide"

# Bad examples ❌
git commit -m "fixed stuff"
git commit -m "WIP"
```

**Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`, `ci`

### Useful Commands

```bash
make format        # Auto-format code
make lint          # Check code quality
make type-check    # Run type checks
make test          # Run tests
make test-cov      # Run tests with coverage
make ci-check      # Run all CI checks locally
```

### Pre-commit Checklist

```bash
# Quick check before committing
make format  # Auto-fix issues
make test    # Ensure tests pass

# Or run everything at once
make ci-check
```

📖 **For more details, see**:
- [Code Quality Quick Reference](code-quality.md) - Commands and troubleshooting
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Full contribution guide

## 📚 Understanding Database Migrations

### What is a Database Migration?

Think of migrations as **version control for your database structure**. Instead of manually creating tables, you write scripts that:

- Create tables, columns, and indexes
- Can be applied in order
- Can be rolled back if needed
- Are tracked in version control

### Why Use Alembic?

- **Industry Standard**: Used in most Python projects
- **Safety**: Changes can be rolled back
- **Team-Friendly**: All team members have the same database structure
- **Production-Ready**: Proven migration process

### Additional Explanation for Korean Developers

Database migrations act like Git for your code. Instead of developers running SQL directly to create or modify tables, changes are managed through migration files. This allows for:

1. **Easier Collaboration**: All team members use the same database schema.
2. **Safer Deployments**: The same schema is applied to staging and production.
3. **Change History Tracking**: You can see when, who, and why a change was made.
4. **Rollbacks**: Easily restore to a previous state if problems arise.

## 🔧 Database Migration Commands

### Using Custom Scripts (Recommended)

**⚠️ Important**: Before running migration commands, make sure your virtual environment is activated:

```bash
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows
```

We provide a convenient script that wraps Alembic commands:

```bash
# Apply all pending migrations
python3 scripts/migrate.py upgrade

# Create a new migration
python3 scripts/migrate.py revision --autogenerate -m "Add user preferences"

# Roll back the last migration
python3 scripts/migrate.py downgrade

# Show migration history
python3 scripts/migrate.py history

# Show the current version
python3 scripts/migrate.py current

# Reset the database (⚠️ Destructive - deletes all data)
python3 scripts/migrate.py reset
```

### Using Alembic Directly

If you prefer to use Alembic directly:

```bash
# Apply migrations
alembic upgrade head

# Create a new migration
alembic revision --autogenerate -m "Description"

# Roll back
alembic downgrade -1

# Show history
alembic history
```

## 🛠️ Development Workflow

### Option 1: Docker Development (Recommended for Beginners)

```bash
# Start everything (Database + Migrations + Server)
docker compose up open-langgraph

# Or start in the background
docker compose up -d open-langgraph
```

**Advantages:**

- ✅ Start everything with one command
- ✅ Migrations run automatically
- ✅ Consistent environment
- ✅ Production-like setup

### Option 2: Local Development (Recommended for Experienced Users)

```bash
# 1. Start the database
docker compose up postgres -d

# 2. Apply new migrations
python3 scripts/migrate.py upgrade

# 3. Start the development server
python3 run_server.py
```

**Advantages:**

- ✅ Full control over each component
- ✅ Easier debugging
- ✅ Faster development cycle
- ✅ Direct access to logs

### Making Database Changes

When you need to change the database structure:

```bash
# 1. Change your code/models

# 2. Create a migration
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"

# 3. Review the generated migration file
# Check: alembic/versions/XXXX_add_new_feature.py

# 4. Apply the migration
python3 scripts/migrate.py upgrade

# 5. Test your changes
python3 run_server.py
```

### Testing Migrations

```bash
# Test the upgrade path
python3 scripts/migrate.py reset  # Start fresh
python3 scripts/migrate.py upgrade  # Apply all

# Test the downgrade path
python3 scripts/migrate.py downgrade  # Roll back one
python3 scripts/migrate.py upgrade    # Re-apply
```

### Workflow Tips for Korean Developers

**Beginners**: Use the Docker option. You can start developing immediately without complex setup.

**Experts**: The local development option gives you individual control over each service, making debugging and performance optimization easier.

**Team Collaboration**: Always commit migration files. After pulling, run `python3 scripts/migrate.py upgrade` to apply the latest schema.

## 📁 Project Structure

```
open-langgraph/
├── alembic/                    # Database migrations
│   ├── versions/              # Migration files
│   ├── env.py                 # Alembic configuration
│   └── script.py.mako         # Migration template
├── src/agent_server/          # Main application code
│   ├── core/database.py       # Database connection
│   ├── api/                   # API endpoints
│   └── models/                # Data models
├── scripts/
│   └── migrate.py             # Migration helper script
├── docs/
│   ├── developer-guide.md     # Original guide
│   ├── developer-guide-en.md  # This file
│   └── migrations.md          # Detailed migration docs
├── alembic.ini                # Alembic configuration
└── docker compose.yml         # Database configuration
```

### Key Directory Descriptions

- **alembic/versions/**: This is where all database schema changes are stored. Each file represents a single migration.
- **src/agent_server/**: This is where the actual application logic resides. API endpoints, business logic, and data models are here.
- **scripts/**: Contains utility scripts to help with development.

## 🔍 Understanding Migration Files

### Migration File Structure

Each migration file in `alembic/versions/` includes:

```python
"""Add user preferences table

Revision ID: 0002
Revises: 0001
Create Date: 2024-01-02 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Runs when applying the migration
    op.create_table('user_preferences',
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('theme', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('user_id')
    )

def downgrade() -> None:
    # Runs when rolling back the migration
    op.drop_table('user_preferences')
```

### Core Concepts

- **Revision ID**: A unique identifier for the migration.
- **Revises**: Points to the previous migration (linked list structure).
- **upgrade()**: The actions to perform when applying the migration.
- **downgrade()**: The actions to perform when rolling back the migration.

### In-depth Explanation for Korean Developers

A migration file defines a **bidirectional transformation**:
- `upgrade()`: Changes the database to a new version.
- `downgrade()`: Restores the database to the previous version.

This is similar to `git commit` and `git revert`. Each migration is linked like a chain, so Alembic runs all necessary migrations in order to get from the current state to the desired state.

**Important**: The `downgrade()` function must perform the exact reverse operation of `upgrade()` for rollbacks to work safely.

## 🚨 Common Issues and Solutions

### Docker Migration Issues

**Problem**: Migration fails in the Docker container.

```bash
# Solution: Check container logs
docker compose logs open-langgraph

# Solution: Run migrations manually for debugging
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py
```

**Problem**: Database connection issues in Docker.

```bash
# Solution: Check if the database is ready
docker compose ps postgres

# Solution: Restart the database
docker compose restart postgres
```

### Database Connection Issues

**Problem**: Cannot connect to the database.

```bash
# Solution: Start the database
docker compose up postgres -d
```

**Problem**: Migration fails with a connection error.

```bash
# Solution: Check if the database is running
docker compose ps postgres

# If not running, start it
docker compose up postgres -d
```

### Migration Issues

**Problem**: "No such revision" error.

```bash
# Solution: Check the current state
python3 scripts/migrate.py current

# If necessary, reset and re-apply
python3 scripts/migrate.py reset
```

**Problem**: Migration conflict.

```bash
# Solution: Check migration history
python3 scripts/migrate.py history

# If necessary, reset (⚠️ Destructive)
python3 scripts/migrate.py reset
```

### Permission Issues

**Problem**: "Permission denied" from the migration script.

```bash
# Solution: Make the script executable
chmod +x scripts/migrate.py
```

### Additional Troubleshooting for Korean Developers

**Problem**: Module not found because the virtual environment is not activated.

```bash
# Solution: Check if the virtual environment is active
which python  # Should show .venv/bin/python

# If not activated
source .venv/bin/activate
```

**Problem**: Conflict with a previous team member's migration.

```bash
# Solution: Pull the latest code and apply migrations
git pull
python3 scripts/migrate.py upgrade
```

## 🧪 Testing Your Changes

### Running Tests

```bash
# Run all tests
pytest

# Run a specific test file
pytest tests/test_api/test_assistants.py

# Run with coverage
pytest --cov=src/agent_server
```

### Testing Database Changes

```bash
# 1. Create a test migration
python3 scripts/migrate.py revision --autogenerate -m "Test feature"

# 2. Apply it
python3 scripts/migrate.py upgrade

# 3. Test the application
python3 run_server.py

# 4. Roll back if there are issues
python3 scripts/migrate.py downgrade
```

### Testing Checklist

1. ✅ Does the migration apply successfully?
2. ✅ Does the application start normally?
3. ✅ Do the API endpoints work as expected?
4. ✅ Does the rollback work correctly?
5. ✅ Do all unit tests pass?

## 🚀 Production Deployment

### Pre-deployment Checklist

1. **Test migrations in staging**:

   ```bash
   # Apply to the staging database
   python3 scripts/migrate.py upgrade
   ```

2. **Back up the production database**:

   ```bash
   # Always back up before migrating
   pg_dump your_database > backup.sql
   ```

3. **Deploy with migrations**:
   ```bash
   # Docker will run migrations automatically
   docker compose up open-langgraph
   ```

### Monitoring

```bash
# Check migration status
python3 scripts/migrate.py current

# View migration history
python3 scripts/migrate.py history
```

### Deployment Guide for Korean Developers

**Precautions for Production Deployment**:

1. **Always back up first**: Data loss is difficult to recover from.
2. **Test in a staging environment first**: Verify in an environment identical to production.
3. **Consider deployment time**: Deploy during off-peak hours.
4. **Prepare a rollback plan**: To quickly recover if problems arise.
5. **Notify the team**: Announce the deployment time and expected downtime in advance.

**Post-deployment Checklist**:
- Verify the application is running normally.
- Monitor logs.
- Test major API endpoints.
- Check data integrity.

## 📖 Best Practices

### Creating Migrations

1. **Always use autogenerate when possible**:

   ```bash
   python3 scripts/migrate.py revision --autogenerate -m "Descriptive message"
   ```

2. **Review the generated migration**:

   - Check the SQL that will be executed.
   - Ensure it matches your intent.
   - Test on a copy of production data.

3. **Use descriptive messages**:

   ```bash
   # Good example
   python3 scripts/migrate.py revision --autogenerate -m "Add user preferences table"

   # Bad example
   python3 scripts/migrate.py revision --autogenerate -m "fix"
   ```

### Code Organization

1. **Keep migrations small**: One logical change per migration.
2. **Test migrations**: Always test both upgrade and downgrade paths.
3. **Document changes**: Use clear migration messages.
4. **Version control**: Commit migration files along with code changes.

### Additional Best Practices for Korean Developers

**Migration Naming Conventions**:
- Write in English, but make the meaning clear.
- Start with a verb: "add", "remove", "modify", "rename".
- Examples: "add_user_avatar_column", "remove_deprecated_status_field".

**Team Collaboration**:
- Pull the latest code before creating a migration.
- Always include migration files in your PR.
- Review the upgrade/downgrade logic of migrations.

**Data Migrations**:
- Separate schema changes from data changes.
- Write large data changes as separate scripts.
- Process in chunks, considering transaction scope.

## 🔗 Useful Resources

### Official Documentation
- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Agent Protocol Specification](https://github.com/langchain-ai/agent-protocol)

### Korean Resources
- [SQLAlchemy Korean Tutorial](https://wikidocs.net/book/5145)
- [FastAPI Korean Guide](https://fastapi.tiangolo.com/ko/)
- [Docker Korean Documentation](https://docs.docker.com/language/ko/)

### Community
- GitHub Issues: For bug reports and feature requests.
- Discussions: For general questions and discussions.
- Discord/Slack: For real-time help (if set up).

## 🆘 Getting Help

### When You're Stuck

1. **Check the logs**:

   ```bash
   docker compose logs postgres
   ```

2. **Check the database state**:

   ```bash
   python3 scripts/migrate.py current
   python3 scripts/migrate.py history
   ```

3. **Reset if necessary** (⚠️ Destructive):

   ```bash
   python3 scripts/migrate.py reset
   ```

4. **Ask for help**:
   - Check existing issues on GitHub.
   - Create a new issue with detailed information.
   - Participate in community discussions.

### Frequently Asked Questions

**Q: Do I need to run migrations every time I start development?**
A: Only when there are new migrations. The Docker setup runs them automatically.

**Q: What if I accidentally mess up the database?**
A: Use `python3 scripts/migrate.py reset` to start fresh (⚠️ all data will be lost).

**Q: How do I know if there are pending migrations?**
A: Use `python3 scripts/migrate.py history` to see all migrations and their status.

**Q: Can I modify an existing migration?**
A: Generally, no. Create a new migration instead. Modifying existing migrations can cause problems.

**Q: What if multiple developers create migrations at the same time?**
A: You might get a Git merge conflict. In this case, coordinate with your team to order the migrations and, if necessary, regenerate one.

**Q: What if a migration fails in production?**
A: Roll back immediately and restore from backup. Then, identify and fix the cause in a staging environment.

---

🎉 **You are now ready to contribute to Open LangGraph!**

Start with small changes, test your migrations, and don't hesitate to ask for help. Happy coding!

---

## 📋 Quick Reference

### Essential Commands

```bash
# Apply all pending migrations
python3 scripts/migrate.py upgrade

# Create a new migration
python3 scripts/migrate.py revision --autogenerate -m "Description"

# Roll back the last migration
python3 scripts/migrate.py downgrade

# Show migration history
python3 scripts/migrate.py history

# Show the current version
python3 scripts/migrate.py current

# Reset the database (⚠️ Destructive - deletes all data)
python3 scripts/migrate.py reset
```

### Daily Development Workflow

**Docker (Recommended):**

```bash
# Start everything
docker compose up open-langgraph
```

**Local Development:**

```bash
# Start the database
docker compose up postgres -d

# Apply migrations
python3 scripts/migrate.py upgrade

# Start the server
python3 run_server.py
```

### Common Patterns

**Add a new table:**

```bash
python3 scripts/migrate.py revision --autogenerate -m "Add users table"
python3 scripts/migrate.py upgrade
```

**Add a column:**

```bash
python3 scripts/migrate.py revision --autogenerate -m "Add email to users"
python3 scripts/migrate.py upgrade
```

**Test migrations:**

```bash
python3 scripts/migrate.py reset
python3 scripts/migrate.py upgrade
```

### Troubleshooting Quick Reference

| Problem                   | Solution                              |
| ---------------------- | ------------------------------------- |
| Cannot connect to DB | `docker compose up postgres -d`       |
| Migration fails      | `python3 scripts/migrate.py current`  |
| Permission denied            | `chmod +x scripts/migrate.py`         |
| Corrupted database      | `python3 scripts/migrate.py reset` ⚠️ |
| Virtual env not active      | `source .venv/bin/activate`           |
| Module not found    | `uv install` then reactivate venv     |

### Environment Setup

**For Docker Development:**

```bash
# Activate virtual environment (Important!)
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows

# Install dependencies
uv install

# Start everything
docker compose up open-langgraph
```

**For Local Development:**

```bash
# Activate virtual environment (Important!)
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows

# Install dependencies
uv install

# Start the database
docker compose up postgres -d

# Apply migrations
python3 scripts/migrate.py upgrade
```

### Code Quality Commands

```bash
# Format code
make format

# Lint check
make lint

# Type check
make type-check

# Security scan
make security

# Run all checks
make ci-check

# Run tests
make test

# Run tests with coverage
make test-cov
```

### Git Workflow

```bash
# Commit changes (auto quality checks)
git add .
git commit -m "feat(api): add new endpoint"

# Manual check before commit
make ci-check

# Auto-fix code
make format
```

### Docker Commands

```bash
# Start all services
docker compose up

# Start only a specific service
docker compose up postgres -d

# View logs
docker compose logs open-langgraph
docker compose logs postgres

# Restart a service
docker compose restart open-langgraph

# Stop and remove everything
docker compose down

# Remove volumes too (deletes data)
docker compose down -v
```

---

## Additional Korean Help

### Development Environment Setup Issues

**Problem**: `uv` not found
```bash
# Solution: Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Problem**: Docker Desktop is not running
```bash
# Solution: Start the Docker Desktop app first
# Mac: Run Docker from Applications
# Windows: Run Docker Desktop from the Start Menu
```

### Performance Optimization Tips

1. **Recommend local execution over Docker during development**
   - Faster feedback loop
   - Real-time code reloading

2. **Database connection pool settings**
   - Connection count can be adjusted with environment variables
   - Use small values for development

3. **Apply migrations frequently**
   - Migrate small changes often
   - Safer than one large change

### Security Considerations

1. **Manage environment variables**
   - Never commit the `.env` file
   - `.env.example` is provided as a template

2. **Database backups**
   - Back up the local development environment periodically
   - Prevents loss of important test data

3. **Protect credentials**
   - Separate credentials for development and production environments
   - Weak passwords can be used locally

We hope this guide was helpful. If you have any questions, feel free to ask on GitHub Issues!
