import os
from utils.db import get_db


MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "migrations"
)


def get_current_version(conn):
    cur = conn.cursor()
    cur.execute("SELECT version FROM schema_version")
    return cur.fetchone()["version"]


def run():
    conn = get_db()
    cur = conn.cursor()

    current = get_current_version(conn)

    files = sorted(
        f for f in os.listdir(MIGRATIONS_DIR)
        if f.endswith(".sql")
    )

    for f in files:
        version = int(f.split("_")[0])
        if version > current:
            path = os.path.join(MIGRATIONS_DIR, f)
            print(f"Applying migration {f}")
            with open(path, "r") as sql:
                conn.executescript(sql.read())
            current = version

    conn.commit()
    conn.close()
    print("Migrations complete.")


if __name__ == "__main__":
    run()
