try:
    print("Testing sync SqliteSaver instantiation...")
    from langgraph.checkpoint.sqlite import SqliteSaver
    import sqlite3
    conn = sqlite3.connect(":memory:")
    memory = SqliteSaver(conn)
    print("Successfully instantiated SqliteSaver")
except Exception as e:
    print(f"Failed to instantiate SqliteSaver: {e}")
    import traceback
    traceback.print_exc()

try:
    print("\nTesting async AsyncSqliteSaver instantiation...")
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
    import aiosqlite
    # Async checkpointers usually take the connection during aput/aget or have a factory
    # In newer langgraph-checkpoint-sqlite, AsyncSqliteSaver.from_conn_string or similar is used
    print("AsyncSqliteSaver imported")
except Exception as e:
    print(f"Failed during AsyncSqliteSaver test: {e}")
