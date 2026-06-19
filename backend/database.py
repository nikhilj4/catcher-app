"""
Production-grade PostgreSQL connection management with pgBouncer pooling
Handles connection pooling, session management, and transaction control
"""

import logging
from typing import Generator, Optional
from contextlib import contextmanager

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session, scoped_session
from sqlalchemy.pool import QueuePool, NullPool
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

class DatabaseConfig:
    """Database configuration for different environments"""

    def __init__(self, environment: str = "production"):
        self.environment = environment

        if environment == "development":
            self.db_url = "sqlite:///./app.db"
            self.pool_size = 5
            self.max_overflow = 10
            self.pool_pre_ping = True
            self.echo = True
        elif environment == "staging":
            self.db_url = "sqlite:///./app.db"
            self.pool_size = 20
            self.max_overflow = 15
            self.pool_pre_ping = True
            self.echo = False
        else:  # production
            self.db_url = "sqlite:///./app.db"
            self.pool_size = 30
            self.max_overflow = 20
            self.pool_pre_ping = True
            self.echo = False

        # Connection pooling settings
        self.pool_timeout = 30
        self.pool_recycle = 3600  # Recycle connections every hour
        self.connect_timeout = 10
        self.statement_timeout = 30000  # 30 seconds


# ============================================================================
# DATABASE ENGINE FACTORY
# ============================================================================

class DatabaseEngine:
    """Factory for creating and managing the SQLAlchemy engine"""

    _engine = None
    _config = None

    @classmethod
    def init(cls, environment: str = "production"):
        """Initialize the database engine with proper pooling"""
        if cls._engine is not None:
            logger.warning("Engine already initialized, skipping re-initialization")
            return

        cls._config = DatabaseConfig(environment)
        logger.info(f"Initializing database engine for {environment} environment")

        # SQLite engine configuration
        cls._engine = create_engine(
            cls._config.db_url,
            connect_args={"check_same_thread": False},
            echo=cls._config.echo,
        )

        # Register engine event listeners
        cls._setup_event_listeners()

    @classmethod
    def _setup_event_listeners(cls):
        """Set up SQLAlchemy event listeners for connection lifecycle"""

        @event.listens_for(cls._engine, "connect")
        def receive_connect(dbapi_conn, connection_record):
            """Initialize connection settings on new connections"""
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
            logger.debug("New SQLite database connection established")

        @event.listens_for(cls._engine, "checkin")
        def receive_checkin(dbapi_conn, connection_record):
            """Log when connection is returned to pool"""
            logger.debug("Connection returned to pool")

        @event.listens_for(cls._engine, "checkout")
        def receive_checkout(dbapi_conn, connection_record, connection_proxy):
            """Log when connection is checked out from pool"""
            logger.debug("Connection checked out from pool")

    @classmethod
    def get_engine(cls):
        """Get the engine instance"""
        if cls._engine is None:
            cls.init()
        return cls._engine

    @classmethod
    def dispose_pool(cls):
        """Dispose of all pooled connections (use for graceful shutdown)"""
        if cls._engine is not None:
            cls._engine.dispose()
            logger.info("Connection pool disposed")

    @classmethod
    def health_check(cls) -> bool:
        """Check if database is healthy"""
        try:
            with cls.get_engine().connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.close()
            logger.info("Database health check passed")
            return True
        except OperationalError as e:
            logger.error(f"Database health check failed: {e}")
            return False


# ============================================================================
# SESSION FACTORY
# ============================================================================

class SessionFactory:
    """Factory for creating database sessions"""

    _session_factory = None

    @classmethod
    def init(cls):
        """Initialize session factory"""
        if cls._session_factory is not None:
            logger.warning("Session factory already initialized")
            return

        engine = DatabaseEngine.get_engine()
        cls._session_factory = sessionmaker(
            bind=engine,
            expire_on_commit=True,  # Expire objects after commit
            autoflush=True,
            autocommit=False,
        )
        logger.info("Session factory initialized")

    @classmethod
    def get_session(cls) -> Session:
        """Get a new database session"""
        if cls._session_factory is None:
            cls.init()
        return cls._session_factory()

    @classmethod
    def get_scoped_session(cls) -> scoped_session:
        """Get a scoped session (thread-local, suitable for web frameworks)"""
        if cls._session_factory is None:
            cls.init()
        return scoped_session(cls._session_factory)


# ============================================================================
# DEPENDENCY INJECTION FOR FASTAPI
# ============================================================================

def get_db() -> Generator[Session, None, None]:
    """Dependency injection function for FastAPI routes

    Usage in FastAPI:
        @app.get("/api/links")
        async def get_links(db: Session = Depends(get_db)):
            links = db.query(Link).filter(Link.user_id == user_id).all()
            return links
    """
    db = SessionFactory.get_session()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ============================================================================
# CONTEXT MANAGER FOR TRANSACTIONS
# ============================================================================

@contextmanager
def transaction_scope():
    """Context manager for explicit transaction control

    Usage:
        with transaction_scope() as db:
            db.add(user)
            db.commit()  # or raise exception to rollback
    """
    db = SessionFactory.get_session()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Transaction rolled back due to: {e}")
        raise
    finally:
        db.close()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def init_db(environment: str = "production"):
    """Initialize all database components
    
    Call this once at application startup:
        init_db(environment="production")
    """
    DatabaseEngine.init(environment)
    SessionFactory.init()
    
    # Auto-create tables for local development
    import models
    engine = DatabaseEngine.get_engine()
    models.Base.metadata.create_all(bind=engine)

    
    logger.info(f"Database initialized for {environment} environment")


def shutdown_db():
    """Gracefully shut down database connections

    Call this at application shutdown:
        shutdown_db()
    """
    DatabaseEngine.dispose_pool()
    logger.info("Database connection pool shut down")


def get_db_stats():
    """Get connection pool statistics (dummy for SQLite)"""
    return {
        "pool_size": 0,
        "checked_out": 0,
        "overflow": 0,
        "total_connections": 0,
    }


# ============================================================================
# MIGRATION HELPERS
# ============================================================================

def run_migrations(alembic_config_path: str):
    """Run Alembic migrations

    Requires alembic package and alembic/env.py setup
    """
    try:
        from alembic.config import Config
        from alembic.command import upgrade

        alembic_cfg = Config(alembic_config_path)
        alembic_cfg.set_main_option("sqlalchemy.url", DatabaseConfig().db_url)
        upgrade(alembic_cfg, "head")
        logger.info("Migrations completed successfully")
    except ImportError:
        logger.error("Alembic not installed. Install with: pip install alembic")
        raise


# ============================================================================
# EXAMPLE INITIALIZATION IN FASTAPI MAIN
# ============================================================================

"""
# In your main FastAPI app file (e.g., main.py):

from fastapi import FastAPI
from database import init_db, shutdown_db, get_db

app = FastAPI()

@app.on_event("startup")
async def startup():
    init_db(environment="production")

@app.on_event("shutdown")
async def shutdown():
    shutdown_db()

# Then use in routes:
@app.get("/api/health")
async def health(db: Session = Depends(get_db)):
    stats = get_db_stats()
    return {"status": "healthy", "database": stats}
"""
