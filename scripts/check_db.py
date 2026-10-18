"""Database schema portability and integrity checker for SQLite and PostgreSQL."""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import Enum, JSON, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from server.app.core.database import Base
import server.app.models  # noqa: F401


def check_database_schema() -> bool:
    all_passed = True
    tables = Base.metadata.tables

    print(f"Checking {len(tables)} tables in Base.metadata...")

    # 1. Foreign Key index coverage
    fk_errors = []
    for table_name, table in tables.items():
        for col in table.columns:
            if col.foreign_keys:
                is_indexed = bool(col.index)
                in_unique_or_index = False
                for c in table.constraints:
                    if isinstance(c, UniqueConstraint) and col.name in [x.name for x in c.columns]:
                        in_unique_or_index = True
                for idx in table.indexes:
                    if col.name in [x.name for x in idx.columns]:
                        in_unique_or_index = True
                if not (is_indexed or in_unique_or_index):
                    fk_errors.append(f"Table '{table_name}', column '{col.name}' has ForeignKey but no index or unique constraint.")

    if fk_errors:
        print("[FAIL] Missing ForeignKey indexes:")
        for err in fk_errors:
            print(f"  - {err}")
        all_passed = False
    else:
        print("[PASS] All ForeignKey columns are indexed or covered by unique constraints.")

    # 2. JSON column check
    json_errors = []
    for table_name, table in tables.items():
        for col in table.columns:
            if "json" in col.name.lower() or isinstance(col.type, JSON):
                # Ensure it's sqlalchemy.JSON and not sqlite specific JSON
                if not isinstance(col.type, JSON):
                    json_errors.append(f"Table '{table_name}', column '{col.name}' is type {type(col.type)}, expected sqlalchemy.JSON")

    if json_errors:
        print("[FAIL] Non-portable JSON columns:")
        for err in json_errors:
            print(f"  - {err}")
        all_passed = False
    else:
        print("[PASS] All JSON columns use portable sqlalchemy.JSON.")

    # 3. Enum column check
    enum_errors = []
    for table_name, table in tables.items():
        for col in table.columns:
            if isinstance(col.type, Enum):
                if getattr(col.type, "native_enum", True):
                    enum_errors.append(
                        f"Table '{table_name}', column '{col.name}' uses native Enum. Use native_enum=False or string fallback."
                    )

    if enum_errors:
        print("[FAIL] Native Enum columns:")
        for err in enum_errors:
            print(f"  - {err}")
        all_passed = False
    else:
        print("[PASS] All enum/choice fields use string fallbacks or portable Enums.")

    # 4. PostgreSQL DDL compilation
    ddl_errors = []
    for table_name, table in tables.items():
        try:
            ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
            if not ddl.strip().startswith("CREATE TABLE"):
                ddl_errors.append(f"Table '{table_name}' generated unexpected DDL.")
        except Exception as exc:
            ddl_errors.append(f"Table '{table_name}' failed PostgreSQL compilation: {exc}")

    if ddl_errors:
        print("[FAIL] PostgreSQL DDL compilation errors:")
        for err in ddl_errors:
            print(f"  - {err}")
        all_passed = False
    else:
        print(f"[PASS] All {len(tables)} tables compiled successfully to PostgreSQL DDL.")

    return all_passed


if __name__ == "__main__":
    success = check_database_schema()
    if not success:
        print("\nDatabase portability check FAILED.")
        sys.exit(1)
    else:
        print("\nDatabase portability check PASSED.")
        sys.exit(0)
