# Migration Commands Quick Reference

> **📚 For complete documentation, see [Developer Guide](developer-guide.md)**

**⚠️ Important**: Always activate your virtual environment first:

```bash
source .venv/bin/activate  # Mac/Linux
# OR .venv/Scripts/activate  # Windows
```

## 🚀 Essential Commands

```bash
# Apply all pending migrations
python3 scripts/migrate.py upgrade

# Create new migration
python3 scripts/migrate.py revision --autogenerate -m "Description"

# Rollback last migration
python3 scripts/migrate.py downgrade

# Show migration history
python3 scripts/migrate.py history

# Show current version
python3 scripts/migrate.py current

# Reset database (⚠️ DESTRUCTIVE)
python3 scripts/migrate.py reset
```

## 🛠️ Daily Workflow

**Docker (Recommended):**

```bash
# Start everything
docker compose up open-langgraph
```

**Local Development:**

```bash
# Start development
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py

# Make database changes
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"
python3 scripts/migrate.py upgrade
```

## 🔍 Quick Troubleshooting

| Problem                   | Solution                              |
| ------------------------- | ------------------------------------- |
| Can't connect to database | `docker compose up postgres -d`       |
| Migration fails           | `python3 scripts/migrate.py current`  |
| Permission denied         | `chmod +x scripts/migrate.py`         |
| Database broken           | `python3 scripts/migrate.py reset` ⚠️ |

## 📚 Need More Help?

- **📖 [Complete Developer Guide](developer-guide.md)** - Full setup, explanations, and troubleshooting
- **🔗 [Alembic Documentation](https://alembic.sqlalchemy.org/)** - Official Alembic docs
