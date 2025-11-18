# Migration Command Quick Reference

> **📚 For the full documentation, see the [Developer Guide](developer-guide.md)**

**⚠️ Important**: Always activate your virtual environment first:

```bash
source .venv/bin/activate  # Mac/Linux
# or .venv/Scripts/activate  # Windows
```

## 🚀 Essential Commands

```bash
# Apply all pending migrations
python3 scripts/migrate.py upgrade

# Create a new migration
python3 scripts/migrate.py revision --autogenerate -m "Description"

# Roll back the last migration
python3 scripts/migrate.py downgrade

# Check migration history
python3 scripts/migrate.py history

# Check the current version
python3 scripts/migrate.py current

# Reset the database (⚠️ Caution: all data will be deleted)
python3 scripts/migrate.py reset
```

## 🛠️ Daily Workflow

**Docker (Recommended for beginners):**

```bash
# Start all services
docker compose up open-langgraph
```

**Local Development Environment (Recommended for advanced users):**

```bash
# Start the development environment
docker compose up postgres -d
python3 scripts/migrate.py upgrade
python3 run_server.py

# After making database changes
python3 scripts/migrate.py revision --autogenerate -m "Add new feature"
python3 scripts/migrate.py upgrade
```

## 🔍 Quick Troubleshooting

| Issue                        | Solution                                |
| --------------------------- | ---------------------------------------- |
| Database connection failed      | `docker compose up postgres -d`          |
| Migration failed           | `python3 scripts/migrate.py current`     |
| Permission denied error              | `chmod +x scripts/migrate.py`            |
| Database corrupted           | `python3 scripts/migrate.py reset` ⚠️    |

## 📚 Need More Help?

- **📖 [Full Developer Guide](developer-guide.md)** - Complete setup, explanations, and troubleshooting
- **🔗 [Alembic Official Documentation](https://alembic.sqlalchemy.org/)** - Official Alembic documentation
