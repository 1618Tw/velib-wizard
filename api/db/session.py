from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings

# Supabase exposes a transaction-mode pgbouncer pooler on port 6543. Each
# transaction may land on a different physical Postgres connection, so
# psycopg3's auto-prepared statements (named "_pg3_N", scoped to the
# physical connection) raise DuplicatePreparedStatement when re-prepared
# after a pool rotation, or InvalidSqlStatementName when reused. Disabling
# auto-prepare avoids the mismatch entirely.
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    future=True,
    connect_args={"prepare_threshold": None},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_session():
    with SessionLocal() as session:
        yield session
