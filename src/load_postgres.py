"""Transactional snapshot and idempotent observation history on PostgreSQL."""

import pandas as pd
from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    delete,
    func,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import insert

from src.errors import LoadError
from src.transform import validate_clean_data


def product_tables():
    try:
        metadata = MetaData()
        tables = []
        for name, history in [("fashion_products", False), ("fashion_observations", True)]:
            tables.append(Table(
                name, metadata, Column("Title", String(200), primary_key=True),
                Column("Price", Float, nullable=False), Column("Rating", Float, nullable=False),
                Column("Colors", Integer, nullable=False), Column("Size", String(8), nullable=False),
                Column("Gender", String(8), nullable=False),
                Column("timestamp", DateTime(timezone=True), primary_key=history, nullable=False),
                CheckConstraint('"Price" > 0'), CheckConstraint('"Rating" BETWEEN 0 AND 5'),
                CheckConstraint('"Colors" BETWEEN 1 AND 100'),
                CheckConstraint('"Gender" IN (\'Men\', \'Women\', \'Unisex\')'),
            ))
        return metadata, tables[0], tables[1]
    except Exception as exc:
        raise LoadError("Cannot define PostgreSQL contract") from exc


def save_to_postgresql(frame, database_url=None, engine=None):
    """Commit both tables together; replay does not duplicate observations."""
    owned = engine is None
    try:
        validate_clean_data(frame)
        if owned:
            engine = create_engine(database_url, pool_pre_ping=True,
                                   connect_args={"connect_timeout": 10})
        if engine.dialect.name != "postgresql":
            raise ValueError("Only PostgreSQL is supported")
        metadata, current, history = product_tables()
        rows = frame.copy()
        rows["timestamp"] = list(pd.to_datetime(rows["timestamp"], utc=True))
        records = rows.to_dict(orient="records")
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            connection.execute(text("SELECT pg_advisory_xact_lock(73190521)"))
            metadata.create_all(connection)
            connection.execute(delete(current))
            connection.execute(current.insert(), records)
            connection.execute(insert(history).values(records).on_conflict_do_nothing())
            count = connection.scalar(select(func.count()).select_from(current))
            if count != len(frame):
                raise ValueError("Read-back row count mismatch")
        return {"status": "success", "rows": count, "table": current.name,
                "history_table": history.name}
    except Exception as exc:
        raise LoadError("PostgreSQL load failed; transaction rolled back") from exc
    finally:
        if owned and engine is not None:
            engine.dispose()
