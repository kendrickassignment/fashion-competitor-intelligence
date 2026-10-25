"""Run against a dedicated disposable DB, never a shared or production database."""

import os

import pandas as pd
import pytest
from sqlalchemy import create_engine, text

from src.errors import LoadError
from src.load_postgres import save_to_postgresql

pytestmark = [pytest.mark.integration,
              pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="Set TEST_DATABASE_URL")]


def test_real_postgres_snapshot_history_idempotence_and_rollback(clean):
    engine = create_engine(os.environ["TEST_DATABASE_URL"])
    try:
        save_to_postgresql(clean, engine=engine)
        save_to_postgresql(clean, engine=engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM fashion_products")) == 1
            assert connection.scalar(text("SELECT count(*) FROM fashion_observations")) == 1
            assert connection.scalar(text('SELECT "Price" FROM fashion_products')) == 1634400.0
        # Valid dataframe but too long for DB column: DELETE must roll back with failed INSERT.
        with pytest.raises(LoadError):
            save_to_postgresql(clean.assign(Title="x" * 201), engine=engine)
        with engine.connect() as connection:
            assert connection.scalar(text('SELECT "Title" FROM fashion_products')) == "T-shirt 2"
        changed = clean.assign(Price=1600000.0, timestamp="2026-10-27T02:00:00.000000Z")
        save_to_postgresql(changed, engine=engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM fashion_products")) == 1
            assert connection.scalar(text("SELECT count(*) FROM fashion_observations")) == 2
        two_products = pd.concat([changed, changed.assign(Title="Jacket 3")], ignore_index=True)
        save_to_postgresql(two_products, engine=engine)
        save_to_postgresql(changed, engine=engine)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM fashion_products")) == 1
    finally:
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS fashion_products, fashion_observations"))
        engine.dispose()
