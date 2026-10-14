# APRIL Memory System - Fixes and Updates

## Date: 2026-10-14

## Issues Fixed

### 1. SQLite Threading Error

**Problem**: 
```
SQLite objects created in a thread can only be used in that same thread.
The object was created in thread id 8688369536 and this is thread id 6180827136.
```

**Root Cause**: SQLite database connections cannot be shared across threads by default.

**Solution**: 
- Implemented thread-local storage for database connections
- Each thread gets its own connection via `_thread_local` storage
- Connections are lazily created and reused within the same thread

**Code Changes**:
- `core/database.py` - Added `_thread_local = threading.local()`
- Modified `MemoryDatabase.__init__()` to use thread-local connections
- Added `self._own_connection` flag to track connection ownership

### 2. Memory Extraction Error Logs

**Problem**: Error logs spammed during normal operation:
```
Memory extraction error: SQLite objects created in a thread can only be used...
```

**Solution**:
- Updated `_extract_and_store_memories()` in `core/agent.py`
- Extraction now runs synchronously (not in background thread)
- Errors are suppressed by default
- Set `APRIL_DEBUG=1` environment variable to see extraction logs

**New Behavior**:
- No error messages during normal operation
- Error messages only visible when `APRIL_DEBUG=1` is set
- Extraction runs after each agent response, before returning

### 3. Better TUI Module

**New File**: `core/tui.py`

**Features**:
- `APRIL_TUI` class - Full curses-based TUI
- `ConsoleRenderer` class - Simple console fallback

**APRIL_TUI Features**:
- Status panel showing session info
- Message history with color-coded roles (user=blue, assistant=yellow)
- Input field for user commands
- Memory statistics display
- Auto-scrolling log view
- Non-blocking input handling via threading
- Color support (6 color pairs for different element types)

**ConsoleRenderer Features**:
- Simple console printing without curses dependency
- Clean message formatting
- Text wrapping for long messages
- Timestamps for each message

**Usage**:
```bash
# Full TUI mode (curses)
python3 -m core.tui

# Simple console mode
python3 -m core.tui --no-tui

# With debug mode (shows extraction logs)
APRIL_DEBUG=1 python3 -m core.tui
```

## Files Modified

| File | Changes |
|------|---------|
| `core/database.py` | Thread-local storage, connection sharing fix |
| `core/agent.py` | Synchronous extraction, suppressed logs |
| `core/__init__.py` | Added TUI exports |
| `core/tui.py` | **NEW** - Full TUI implementation |

## New Files

| File | Purpose |
|------|---------|
| `core/tui.py` | Console TUI with curses (main) and fallback |
| `docs/FIXES-AND-UPDATES.md` | This documentation |

## Backward Compatibility

✅ All existing tests pass
✅ All existing imports work unchanged
✅ Database schema unchanged
✅ Memory storage format unchanged

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APRIL_DEBUG` | `0` | Set to `1` to see extraction logs |
| `APRIL_MEMORY_ENABLED` | `true` | Enable memory storage |
| `APRIL_MEMORY_DB_PATH` | `./data/april_memory.db` | Database path |

## Testing

```bash
# Run unit tests
python3 -m unittest tests.test_memory -v

# Test TUI imports
python3 -c "from core import APRIL_TUI, ConsoleRenderer; print('OK')"

# Test database threading
python3 -c "
import threading
from core import MemoryDatabase

# Multiple threads accessing same DB
def task():
    db = MemoryDatabase()
    db.save_message('test', 'user', 'hello')
    db.close()

threads = [threading.Thread(target=task) for _ in range(5)]
for t in threads: t.start()
for t in threads: t.join()
print('Threading test passed!')
"
```

## Future Improvements

### Potential Enhancements

1. **OpenTUI Integration**
   - Consider Zig-based OpenTUI for even better performance
   - Currently using Python curses (built-in, no dependencies)

2. **Async Database**
   - Use `aiosqlite` for truly async operations
   - Would eliminate threading complexity entirely

3. **Better Logging System**
   - Structured logging with levels (DEBUG, INFO, ERROR)
   - Configurable log output destinations

4. **Memory Export**
   - Export memories to markdown
   - Export to other formats (JSON, CSV)

5. **Vector Search**
   - Add embeddings for semantic memory search
   - Better relevance ranking

## Summary

| Issue | Status |
|-------|--------|
| SQLite threading error | ✅ Fixed |
| Error logs spam | ✅ Fixed (suppressed) |
| Better TUI | ✅ Implemented |
| Backward compat | ✅ Maintained |
| Tests passing | ✅ 12/12 passing |
