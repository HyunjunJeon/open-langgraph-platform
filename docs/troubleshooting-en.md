# Troubleshooting Guide

This document covers common issues and their solutions when using Open LangGraph.

## Table of Contents

- [Database Issues](#database-issues)
- [Graph Execution Issues](#graph-execution-issues)
- [Streaming Issues](#streaming-issues)
- [Authentication Issues](#authentication-issues)
- [Environment Setup Issues](#environment-setup-issues)

---

## Database Issues

### 1. Database Connection Failure

**Symptom:**
```
sqlalchemy.exc.OperationalError: could not connect to server
```

**Cause:**
- PostgreSQL server is not running
- Incorrect database connection information
- Firewall or network issues

**Solution:**

1. Check if PostgreSQL is running:
```bash
# If running with Docker
docker compose ps postgres

# If not running, start it
docker compose up postgres -d
```

2. Check the database connection information:
```bash
# Check the .env file
cat .env | grep DATABASE_URL

# Correct format: postgresql+asyncpg://user:password@host:port/database
```

3. Test the database connection directly:
```bash
# Test connection with psql
psql postgresql://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db
```

**Prevention:**
- Use the correct connection string by referring to `.env.example`.
- Maintain consistency by managing the database with Docker Compose.
- Periodically monitor with the health check endpoint (`/health`).

---

### 2. Migration Error

**Symptom:**
```
alembic.util.exc.CommandError: Can't locate revision identified by 'xxx'
```

**Cause:**
- Missing or corrupted migration file
- Mismatch between database and migration versions
- Virtual environment not activated

**Solution:**

1. Check the current migration status:
```bash
# Activate virtual environment (Important!)
source .venv/bin/activate

# Check current version
python3 scripts/migrate.py current

# Check migration history
python3 scripts/migrate.py history
```

2. Re-apply migrations:
```bash
# Upgrade to the latest version
python3 scripts/migrate.py upgrade
```

3. Reset the database in a development environment (Caution: all data will be deleted):
```bash
python3 scripts/migrate.py reset
```

4. If a migration file is corrupted:
```bash
# Check migration files
ls -la alembic/versions/

# Restore from Git
git checkout -- alembic/versions/
```

**Prevention:**
- Always run migrations after activating the virtual environment.
- Version control migration files with Git.
- Utilize automatic migrations when using Docker.
- Test in a staging environment before applying to production.

---

### 3. Checkpointer Initialization Failure

**Symptom:**
```
RuntimeError: Checkpointer setup failed
```

**Cause:**
- LangGraph tables were not created
- Insufficient database permissions
- URL format mismatch (postgresql:// vs postgresql+asyncpg://)

**Solution:**

1. Check database permissions:
```sql
-- Check with psql
\du open_langgraph_user

-- Required permissions: CREATEDB, CREATE TABLE
```

2. Manually create LangGraph tables:
```python
# Run in a Python interpreter
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore

# Connection string (psycopg format)
conn_string = "postgresql://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db"

# Create tables
import asyncio
async def setup():
    async with AsyncPostgresSaver.from_conn_string(conn_string) as saver:
        await saver.setup()
    async with AsyncPostgresStore.from_conn_string(conn_string) as store:
        await store.setup()

asyncio.run(setup())
```

3. Restart the server:
```bash
# Docker
docker compose restart open-langgraph

# Local development
uvicorn src.agent_server.main:app --reload
```

**Prevention:**
- Run the migration script during initial setup.
- Grant sufficient permissions to the database user.
- `DatabaseManager` is implemented to automatically call `.setup()`.

---

## Graph Execution Issues

### 1. Graph Loading Failure

**Symptom:**
```
ValueError: Graph 'my_agent' not found in registry
```

**Cause:**
- Graph not registered in `open_langgraph.json`
- Incorrect graph file path
- `graph` variable not defined in the graph module

**Solution:**

1. Check `open_langgraph.json`:
```json
{
  "graphs": {
    "my_agent": "./graphs/my_agent.py:graph"
  }
}
```

2. Check if the graph file exists:
```bash
ls -la graphs/my_agent.py
```

3. Check if the graph is defined correctly:
```python
# graphs/my_agent.py
from langgraph.graph import StateGraph

workflow = StateGraph(MyState)
# ... define nodes and edges

# Must be exported as 'graph' variable
graph = workflow.compile()
```

4. Manually test the graph:
```python
# In a Python interpreter
from graphs.my_agent import graph
print(graph)  # Check if it loads correctly
```

**Prevention:**
- Refer to the example (`graphs/react_agent/`) when creating a new graph.
- Restart the server after registering a graph.
- Verify graph loading with unit tests.

---

### 2. Interrupt Not Working

**Symptom:**
- Graph continues to run after `interrupt()` is called
- Human-in-the-Loop (HITL) functionality not working

**Cause:**
- Graph compiled without a checkpointer
- Incorrect interrupt condition
- Client not checking for interrupt status

**Solution:**

1. Check if a checkpointer is set:
```python
# Check if the config includes a checkpointer when running the graph in the service
config = {
    "configurable": {
        "thread_id": thread_id,
        "checkpoint_id": checkpoint_id
    }
}

# LangGraphService automatically injects the checkpointer
```

2. Check the interrupt condition:
```python
# Call interrupt in the node
from langgraph.types import interrupt

def approval_node(state):
    # If user approval is needed
    user_input = interrupt("Approve this action?")
    # On resume, user_input will have the value
    return {"approved": user_input}
```

3. Check the thread status:
```bash
# Check the current status via API
curl http://localhost:8000/threads/{thread_id}/state
```

4. Resume the interrupt:
```python
# Send an update from the client
import requests

response = requests.post(
    f"http://localhost:8000/threads/{thread_id}/runs",
    json={
        "assistant_id": assistant_id,
        "input": {"approval": True}  # Interrupt response
    }
)
```

**Prevention:**
- Refer to the `graphs/react_agent_hitl/` example.
- Always use a checkpointer for graphs with interrupts.
- Check the `next` field in the client for interrupt status.

---

### 3. Graph Infinite Loop

**Symptom:**
- Graph execution does not terminate
- Timeout error occurs

**Cause:**
- No termination condition in a cyclic edge
- No path to the `END` node
- Error in conditional edge logic

**Solution:**

1. Visualize the graph structure:
```python
# Print the graph in Mermaid format
from langraph.graph import StateGraph

print(graph.get_graph().draw_mermaid())
```

2. Add a termination condition:
```python
from langgraph.graph import END

def should_continue(state):
    # Set a maximum number of iterations
    if state.get("iterations", 0) > 10:
        return END
    return "next_node"

workflow.add_conditional_edges(
    "my_node",
    should_continue,
    {END: END, "next_node": "next_node"}
)
```

3. Set an execution limit:
```python
# Limit the maximum number of steps
config = {
    "recursion_limit": 50  # Default: 25
}

result = await graph.ainvoke(input, config)
```

**Prevention:**
- Set clear termination conditions for all cyclic paths.
- Draw a state diagram when designing the graph.
- Verify various scenarios with unit tests.
- Set an appropriate recursion limit.

---

## Streaming Issues

### 1. SSE Connection Dropped

**Symptom:**
- Connection suddenly terminates during streaming
- `EventSource` error on the client side

**Cause:**
- Unstable network
- Proxy/load balancer timeout
- Stream interrupted due to a server error

**Solution:**

1. Implement reconnection logic (client):
```javascript
const eventSource = new EventSource(`http://localhost:8000/threads/${threadId}/runs/${runId}/stream`);

eventSource.onerror = (error) => {
  console.error('SSE error:', error);

  // Automatic reconnection (EventSource tries to reconnect by default)
  // Can resume with Last-Event-ID
};

eventSource.addEventListener('end', () => {
  eventSource.close();
});
```

2. Replay from the event store:
```bash
# Stream from a specific event ID
curl "http://localhost:8000/threads/{thread_id}/runs/{run_id}/stream?after_event_id=123"
```

3. Check server logs:
```bash
# Docker logs
docker compose logs -f open-langgraph

# Check for error messages
```

**Prevention:**
- Implement reconnection logic on the client.
- Utilize the `Last-Event-ID` header.
- Increase proxy timeout settings (e.g., nginx `proxy_read_timeout`).
- Adjust the automatic cleanup interval of the EventStore.

---

### 2. Missing Events

**Symptom:**
- Some events do not arrive at the client
- Stream is incomplete

**Cause:**
- Some events lost due to network latency
- Event storage failure
- Client buffer overflow

**Solution:**

1. Check the event store:
```sql
-- Query events from the database
SELECT * FROM sse_events
WHERE run_id = 'your-run-id'
ORDER BY sequence_number;
```

2. Get all events again after completion:
```bash
# Replay all events from the beginning
curl "http://localhost:8000/threads/{thread_id}/runs/{run_id}/stream"
```

3. Verify event order (client):
```javascript
let lastSequence = -1;

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);

  // Check sequence number
  if (data.sequence !== lastSequence + 1) {
    console.warn('Event sequence gap detected');
    // Reconnection or replay logic
  }

  lastSequence = data.sequence;
};
```

**Prevention:**
- Utilize permanent storage via EventStore.
- Verify sequence numbers on the client.
- Double-check with a final state query for data integrity.
- For important data, double-check by querying the final state.

---

### 3. Reconnection Failure

**Symptom:**
- 404 error on reconnection after a disconnect
- Cannot resume from previous events

**Cause:**
- Event already deleted (cleanup task)
- Incorrect run_id or thread_id
- Event store error

**Solution:**

1. Check the Run status:
```bash
# Check if the Run still exists
curl http://localhost:8000/threads/{thread_id}/runs/{run_id}
```

2. Check the event retention period:
```python
# src/agent_server/services/event_store.py
# Check EVENT_RETENTION_HOURS setting (default: 24 hours)
```

3. Start a new stream:
```bash
# If the event is deleted, create a new run
curl -X POST http://localhost:8000/threads/{thread_id}/runs \
  -H "Content-Type: application/json" \
  -d '{"assistant_id": "your-assistant-id"}'
```

**Prevention:**
- Set an appropriate event retention period.
- Store important execution results separately.
- Check the run status before attempting to reconnect.
- Create a new run if timed out.

---

## Authentication Issues

### 1. Token Validation Failure

**Symptom:**
```
401 Unauthorized: Invalid authentication credentials
```

**Cause:**
- Incorrect or expired token
- Incorrect Authorization header format
- Authentication type mismatch

**Solution:**

1. Check the authentication type:
```bash
# Check the .env file
cat .env | grep AUTH_TYPE

# noop: no authentication (for development)
# custom: custom authentication
```

2. Disable authentication for development:
```bash
# Set in .env
AUTH_TYPE=noop
```

3. If using custom authentication, check the token format:
```bash
# Correct header format
curl -H "Authorization: Bearer your-token" http://localhost:8000/assistants
```

4. Check the authentication logic in `auth.py`:
```python
# auth.py
@auth.authenticate
async def authenticate(authorization: str | None) -> Auth.types.MinimalUserDict:
    # Check token validation logic
    # Add debug log
    print(f"Received token: {authorization}")
    ...
```

**Prevention:**
- Use `AUTH_TYPE=noop` in development environments.
- Manage tokens securely in production.
- Implement token expiration and renewal logic.
- Return clear error messages on authentication failure.

---

### 2. Authorization Error

**Symptom:**
```
403 Forbidden: Access denied
```

**Cause:**
- User does not have permission for the resource
- Error in `@auth.on` decorator settings
- Multi-tenancy isolation failure

**Solution:**

1. Check the user context:
```python
# Debugging: print current user information
from src.agent_server.core.auth import get_current_user

user = await get_current_user(request)
print(f"User: {user}")
```

2. Check the authorization logic in `auth.py`:
```python
@auth.on.threads.read
async def authorize_thread_read(
    ctx: Auth.types.AuthContext,
    thread_id: str
) -> bool:
    # Check authorization logic
    # Debug log
    print(f"User {ctx.user['user_id']} accessing thread {thread_id}")
    ...
```

3. Check resource ownership:
```sql
-- Check in the database
SELECT * FROM thread_metadata WHERE thread_id = 'your-thread-id';
```

**Prevention:**
- Store owner information for all resources.
- Automatically filter by user in the `authorize()` function.
- Write authorization test cases.
- Enforce multi-tenancy isolation at the database level.

---

### 3. Multi-tenancy Isolation Issue

**Symptom:**
- Data from other users is visible
- Data leakage or mixing

**Cause:**
- Missing user context injection
- Missing user filter in database queries
- `user_id` not included in LangGraph config

**Solution:**

1. Check for user information in the Config:
```python
# Check the config when running LangGraph
config = {
    "configurable": {
        "thread_id": thread_id,
        "user_id": user.user_id  # Must be included
    }
}
```

2. Filter database queries:
```python
# Apply user filter to all queries
query = select(ThreadMetadata).where(
    ThreadMetadata.user_id == user.user_id
)
```

3. Use `inject_user_context()`:
```python
from src.agent_server.services.langgraph_service import inject_user_context

# Automatically inject user context
config = inject_user_context(base_config, user)
```

4. Check checkpointer/store isolation:
```python
# LangGraph automatically isolates by user_id in the config
# But metadata tables need manual filtering
```

**Prevention:**
- Use the `get_current_user()` dependency in all API endpoints.
- Always apply a user_id filter to database queries.
- Utilize the `inject_user_context()` utility function.
- Verify isolation with integration tests (test with different users).

---

## Environment Setup Issues

### 1. Environment Variable Not Set

**Symptom:**
```
KeyError: 'DATABASE_URL'
pydantic.error_wrappers.ValidationError: field required
```

**Cause:**
- `.env` file missing or not loaded
- Required environment variable not set

**Solution:**

1. Create a `.env` file:
```bash
# Start by copying .env.example
cp .env.example .env

# Set required values
vim .env
```

2. Check required environment variables:
```bash
# Minimum required items
DATABASE_URL=postgresql+asyncpg://open_langgraph_user:open_langgraph_password@localhost:5432/open_langgraph_db
OPENAI_API_KEY=your-openai-api-key
AUTH_TYPE=noop  # or custom
```

3. Check if environment variables are loaded:
```python
# Test in Python
import os
from dotenv import load_dotenv

load_dotenv()
print(os.getenv('DATABASE_URL'))
```

4. If using Docker:
```yaml
# Check env_file in docker-compose.yml
services:
  open-langgraph:
    env_file:
      - .env
```

**Prevention:**
- Refer to `.env.example` when starting a project.
- Add `.env` to `.gitignore` (already included).
- Document required environment variables in the README.
- Validate environment variables in the startup script.

---

### 2. open_langgraph.json Error

**Symptom:**
```
json.decoder.JSONDecodeError: Expecting property name enclosed in double quotes
ValueError: Invalid graph configuration
```

**Cause:**
- JSON syntax error
- Incorrect file path
- Missing required fields

**Solution:**

1. Validate JSON syntax:
```bash
# Validate with jq
cat open_langgraph.json | jq .

# Validate with Python
python3 -c "import json; json.load(open('open_langgraph.json'))"
```

2. Check the correct format:
```json
{
  "graphs": {
    "agent_id": "./graphs/agent_file.py:graph"
  },
  "auth": {
    "path": "./auth.py:auth"
  },
  "env": ".env",
  "dependencies": [
    "langchain-openai",
    "langchain-community"
  ]
}
```

3. Check file paths:
```bash
# Check if relative paths are correct
ls -la ./graphs/agent_file.py
ls -la ./auth.py
```

4. Validate the schema:
```python
# LangGraphService validates automatically
# Check server startup logs
```

**Prevention:**
- Use a linter when editing JSON (VSCode, IDE).
- Refer to the example file when writing.
- Use relative paths from the `open_langgraph.json` location.
- Version control with Git to track changes.

---

### 3. Dependency Conflict

**Symptom:**
```
pip._vendor.resolvelib.resolvers.ResolutionImpossible
ModuleNotFoundError: No module named 'xxx'
```

**Cause:**
- Package version conflict
- Incompatible dependencies
- Virtual environment issue

**Solution:**

1. Recreate the virtual environment:
```bash
# Delete the existing environment
rm -rf .venv

# Reinstall
uv install
```

2. Check dependency versions:
```bash
# Currently installed packages
uv pip list

# Check pyproject.toml
cat pyproject.toml
```

3. Reinstall a specific package:
```bash
# Reinstall a problematic package
uv pip install --force-reinstall langchain-openai
```

4. Clear the cache:
```bash
# Delete pip cache
uv cache clean
```

5. If using Docker:
```bash
# Rebuild the image (without cache)
docker compose build --no-cache open-langgraph
```

**Prevention:**
- Manage dependencies with `uv` (fast and stable).
- Specify version ranges in `pyproject.toml`.
- Always work with the virtual environment activated.
- Periodically check for conflicts with `uv pip check`.
- Test in a clean environment before production deployment.

---

## General Debugging Tips

### Check Logs

```bash
# Docker logs
docker compose logs -f open-langgraph

# Logs for a specific time range
docker compose logs --since 10m open-langgraph

# uvicorn logs in local development
# Output to the console by default
```

### Health Check

```bash
# Check the overall system status
curl http://localhost:8000/health

# Example response:
# {
#   "status": "healthy",
#   "database": "ok",
#   "checkpointer": "ok",
#   "store": "ok"
# }
```

### Direct Database Access

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U open_langgraph_user -d open_langgraph_db

# Check tables
\dt

# Check schema
\d table_name
```

### Using a Python Debugger

```python
# Add a breakpoint in the code
import pdb; pdb.set_trace()

# Or Python 3.7+
breakpoint()
```

### Checking in an Isolated Environment with Tests

```bash
# Test only a specific feature
uv run pytest tests/test_api/test_threads.py -v

# Rerun only failed tests
uv run pytest --lf

# Test with coverage
uv run pytest --cov=src --cov-report=html
```

---

## Additional Support

If the issue is not resolved:

1. **GitHub Issues**: Search or create an issue in the [project repository](https://github.com/your-repo/open-langgraph).
2. **Documentation**: Refer to other guides in the `docs/` directory.
3. **Log Collection**: Attach relevant logs and configuration files when reporting an issue.
4. **Reproduction Steps**: Provide minimal steps to reproduce the issue.

---

**Last Updated**: 2025-10-27
