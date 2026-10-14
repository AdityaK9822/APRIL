# APRIL Cross-Session Memory Implementation

## Overview

APRIL now features **cross-session memory** that allows the agent to remember important information across different conversations. This enables:

- **Persistent conversations**: Key facts and preferences are remembered between sessions
- **Automatic knowledge extraction**: Contextual insights are automatically extracted from conversations
- **Context augmentation**: Relevant past memories are automatically included in future conversations
- **Flexible storage**: Memories stored as JSON for machine processing, with optional markdown conversion

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        User Request                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Agent Runtime                             │
│  - Augments context with relevant memories                   │
│  - Saves user message                                        │
│  - Runs conversation loop                                    │
│  - Saves assistant response                                  │
│  - Triggers background memory extraction                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ├─────────────► Database (SQLite)
                       │                   ├── conversations (raw)
                       │                   ├── memory (structured)
                       │                   └── sessions (metadata)
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 Memory Extraction (LLM)                      │
│  - Analyzes conversation turns                              │
│  - Extracts facts, decisions, solutions, preferences        │
│  - Calculates confidence scores                             │
│  - Generates tags for searchability                          │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Context Augmentation                       │
│  - Retrieves relevant memories for new requests              │
│  - Injects into conversation context                         │
│  - Improves continuity across sessions                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Files Created

### 1. `core/database.py`

SQLite database for conversation storage and extracted memories.

**Tables**:
- `conversations`: Temporary raw message buffer
- `memory`: Permanent structured knowledge
- `sessions`: Session metadata

**Key Methods**:
- `save_message(session_id, role, content)` - Save conversation turn
- `get_unprocessed_messages(session_id)` - Get unprocessed messages
- `save_memory(...)` - Save extracted memory
- `get_memories(...)` - Retrieve memories with filtering
- `search_memories(query)` - Text search in memories
- `save_session(session_id, metadata)` - Save session metadata
- `get_stats()` - Database statistics

### 2. `core/memory_extractor.py`

Extracts structured knowledge from conversations using LLM.

**Key Features**:
- **Extraction Types**: fact, decision, solution, preference
- **Confidence Scoring**: 0.0-1.0 for each extraction
- **Tag Generation**: Automatic tag extraction for searchability
- **Fallback Mode**: Graceful degradation when LLM unavailable

**Key Methods**:
- `extract(messages)` - Extract from conversation
- `format_conversation(messages)` - Format for LLM prompt
- `_validate_extraction(extraction)` - Validate extraction structure

### 3. `core/memory_extractor.py` (Updated)

**Updated Files**:
- `core/config.py` - Added memory configuration options
- `core/session.py` - Added database integration
- `core/__init__.py` - Exported new modules

### 4. `tests/test_memory.py`

Comprehensive test suite with 12 tests:
- Database operations (8 tests)
- Memory extraction (4 tests)
- Integration tests

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APRIL_MEMORY_ENABLED` | `true` | Enable cross-session memory |
| `APRIAL_MEMORY_DB_PATH` | `./data/april_memory.db` | Path to SQLite database |
| `APRIL_MEMORY_EXTRACTION_MODEL` | `gemma4:31b-cloud` | LLM for memory extraction |
| `APRIL_MEMORY_CLEANUP_DELAY` | `60` | Seconds before cleanup |
| `APRIL_MEMORY_MAX_CONTEXT` | `10` | Max memories in context |

### Configuration Example

```python
from core.config import AgentConfig

config = AgentConfig(
    model="gemma4:31b-cloud",
    api_key="your-key",
    api_base_url="http://localhost:11434/v1",
    memory_enabled=True,
    memory_db_path="./data/april_memory.db",
    memory_extraction_model="gemma4:31b-cloud",
    memory_cleanup_delay=60,
    memory_max_context=10
)
```

---

## Usage Examples

### Basic Usage

```python
from core import AgentConfig, AgentRuntime

# Create config with memory enabled
config = AgentConfig.from_env()  # Reads from .env

# Create agent - memory is automatically enabled
agent = AgentRuntime(config)

# Run conversation - memories are automatically saved
response = agent.run("What's the current date?")
print(response)

# Check statistics
if agent.db:
    stats = agent.db.get_stats()
    print(f"Messages: {stats['total_messages']}")
    print(f"Memories: {stats['total_memories']}")
```

### Searching Memories

```python
# Search for memories by keyword
memories = agent.db.search_memories("model configuration")

for mem in memories:
    print(f"[{mem['memory_type']}] {mem['content']['text']}")
    print(f"  Tags: {mem['tags']}")
    print(f"  Confidence: {mem['confidence']}")
```

### Manual Memory Extraction

```python
from core.memory_extractor import MemoryExtractor

extractor = MemoryExtractor()

# Extract from conversation
messages = [
    {"role": "user", "content": "I prefer the dark mode"},
    {"role": "assistant", "content": "Dark mode has been enabled."}
]

memories = extractor.extract(messages, client=agent.client)

for mem in memories:
    agent.db.save_memory(
        session_id=agent.session.id,
        memory_type=mem['type'],
        content=mem['content'],
        confidence=mem['confidence'],
        tags=mem['tags']
    )
```

### Retrieving Relevant Context

```python
# Get relevant memories for current query
memories = agent.session.get_relevant_memories(
    user_input="What settings are configured?",
    limit=5
)
```

---

## Memory Extraction Schema

```json
{
  "type": "fact" | "decision" | "solution" | "preference",
  "content": {
    "text": "Extracted information"
  },
  "confidence": 0.9,
  "tags": ["tag1", "tag2"],
  "source_message_ids": [1, 2]
}
```

### Type Definitions

| Type | Description | Example |
|------|-------------|---------|
| `fact` | Objective information learned | "User prefers VS Code editor" |
| `decision` | Choices made during conversation | "Decided to use PostgreSQL" |
| `solution` | Problems solved or approaches identified | "Fixed bug by increasing timeout" |
| `preference` | User preferences detected | "User wants local-first approach" |

---

## Cleanup Policy

1. **Raw messages** marked as processed after extraction
2. **Processed messages** kept for configurable delay (default 60 seconds)
3. **Memories** stored permanently (no automatic deletion)
4. **Sessions** metadata stored permanently

Cleanup runs automatically in background thread after extraction.

---

## Extension Points

### Adding New Memory Types

1. Add type to extraction prompt in `memory_extractor.py`
2. Handle in memory save logic
3. Update search/filtering

### Memory-to-Markdown Conversion

```python
def memory_to_markdown(memory):
    """Convert memory to human-readable markdown"""
    return f"""### [{memory['memory_type'].upper()}] {memory['content'].get('text', '')}

**Confidence**: {memory['confidence']}
**Tags**: {', '.join(memory['tags'])}
**Created**: {memory['created_at']}
"""
```

### Vector Search Integration

```python
# future: Add vector embeddings for semantic search
import sqlite_vec
# Create vector embeddings for memory content
# Search by semantic similarity instead of keyword
```

---

## Testing

Run tests:
```bash
python3 -m unittest tests.test_memory -v
```

Expected output:
```
Ran 12 tests in X.XXXs

OK
```

---

## Troubleshooting

### Memory Not Saving

1. Check `config.memory_enabled` is `True`
2. Verify database path is writable: `ls -la ./data/`
3. Check for error messages during agent initialization

### Extraction Failed

1. Ensure OpenAI-compatible endpoint is running
2. Check model name in `memory_extraction_model` config
3. Extraction has fallback mode - returns empty list on error

### Old Data Not Found

1. Memories are stored per-session
2. Search across all sessions: `db.search_memories("query")`
3. Check session ID in conversation context

---

## Future Enhancements

1. **Vector Search**: Semantic similarity search over memories
2. **Periodic Summarization**: Auto-summarize old memories
3. **Memory Expiration**: Configurable retention policies
4. **Memory Priority**: Weight memories by relevance/recency
5. **Export to Markdown**: Human-readable memory export

---

## Changelog

- **v1.0.0** (Current)
  - SQLite-based memory storage
  - LLM-assisted memory extraction
  - Background cleanup of processed messages
  - Context augmentation with relevant memories
  - Comprehensive test suite
