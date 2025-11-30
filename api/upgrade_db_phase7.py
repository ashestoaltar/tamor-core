import os
import sqlite3
from datetime import datetime

# If you use python-dotenv in server.py, this matches that behavior.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed or not used. Using default DB path.")

# --- CONFIG -----------------------------------------------------------------

# Path to your SQLite DB.
# If MEMORY_DB is set in .env, use that. Otherwise default to "memory.db".
DB_PATH = os.getenv("MEMORY_DB", "memory/tamor.db")

# IMPORTANT:
# This should be the name of your existing memory table.
# Common guesses: "memories", "memory", or "embedding_memory".
# Change this to match your actual table name if needed.
EXISTING_MEMORY_TABLE = "memories"

# --- HELPERS ----------------------------------------------------------------

def column_exists(cursor, table_name: str, column_name: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table_name});")
    cols = cursor.fetchall()
    for col in cols:
        # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
        if col[1].lower() == column_name.lower():
            return True
    return False

def table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
        (table_name,)
    )
    return cursor.fetchone() is not None

# --- MAIN UPGRADE LOGIC -----------------------------------------------------

def main():
    print(f"[*] Connecting to DB at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # 1) USERS TABLE ------------------------------------------------------
        if not table_exists(cursor, "users"):
            print("[+] Creating table: users")
            cursor.execute(
                """
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    password_hash TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
        else:
            print("[=] Table already exists: users")

        # 2) PROJECTS TABLE ---------------------------------------------------
        if not table_exists(cursor, "projects"):
            print("[+] Creating table: projects")
            cursor.execute(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
                """
            )
        else:
            print("[=] Table already exists: projects")

        # 3) CONVERSATIONS TABLE ----------------------------------------------
        if not table_exists(cursor, "conversations"):
            print("[+] Creating table: conversations")
            cursor.execute(
                """
                CREATE TABLE conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    project_id INTEGER,
                    title TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
                );
                """
            )
        else:
            print("[=] Table already exists: conversations")

        # 4) MESSAGES TABLE ---------------------------------------------------
        if not table_exists(cursor, "messages"):
            print("[+] Creating table: messages")
            cursor.execute(
                """
                CREATE TABLE messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL,
                    sender TEXT NOT NULL,        -- 'user' or 'tamor'
                    role TEXT NOT NULL,          -- 'user', 'assistant', 'system'
                    content TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                );
                """
            )
        else:
            print("[=] Table already exists: messages")

        # 5) INDEXES FOR PERFORMANCE ------------------------------------------
        print("[*] Ensuring indexes exist (if not, they will be created).")

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_conversations_user
            ON conversations(user_id);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_projects_user
            ON projects(user_id);
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id);
            """
        )

        # 6) EXTEND EXISTING MEMORY TABLE (OPTIONAL BUT RECOMMENDED) ----------
        # We will add user_id, conversation_id, and message_id columns
        # to the existing memory table so memories can be scoped per user and conversation.
        print(f"[*] Checking existing memory table: {EXISTING_MEMORY_TABLE}")

        if table_exists(cursor, EXISTING_MEMORY_TABLE):

            # user_id column
            if not column_exists(cursor, EXISTING_MEMORY_TABLE, "user_id"):
                print(f"[+] Adding column user_id to {EXISTING_MEMORY_TABLE}")
                cursor.execute(
                    f"ALTER TABLE {EXISTING_MEMORY_TABLE} ADD COLUMN user_id INTEGER;"
                )
            else:
                print(f"[=] Column user_id already exists on {EXISTING_MEMORY_TABLE}")

            # conversation_id column
            if not column_exists(cursor, EXISTING_MEMORY_TABLE, "conversation_id"):
                print(f"[+] Adding column conversation_id to {EXISTING_MEMORY_TABLE}")
                cursor.execute(
                    f"ALTER TABLE {EXISTING_MEMORY_TABLE} ADD COLUMN conversation_id INTEGER;"
                )
            else:
                print(f"[=] Column conversation_id already exists on {EXISTING_MEMORY_TABLE}")

            # message_id column
            if not column_exists(cursor, EXISTING_MEMORY_TABLE, "message_id"):
                print(f"[+] Adding column message_id to {EXISTING_MEMORY_TABLE}")
                cursor.execute(
                    f"ALTER TABLE {EXISTING_MEMORY_TABLE} ADD COLUMN message_id INTEGER;"
                )
            else:
                print(f"[=] Column message_id already exists on {EXISTING_MEMORY_TABLE}")

        else:
            print(f"[!] WARNING: Memory table '{EXISTING_MEMORY_TABLE}' not found.")
            print("    If your memory/embeddings table has a different name,")
            print("    edit EXISTING_MEMORY_TABLE at the top of this script and run again.")

        # COMMIT ALL CHANGES --------------------------------------------------
        conn.commit()
        print("[✓] Database upgrade for Phase 7.1 completed successfully.")

    except Exception as e:
        print("[X] Error during upgrade, rolling back.")
        conn.rollback()
        raise
    finally:
        conn.close()
        print("[*] Connection closed.")

if __name__ == "__main__":
    main()
