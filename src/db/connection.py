import os
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

# Create a thread-safe connection pool (min 1, max 20 connections)
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 20,
        host=os.getenv("DB_HOST", "localhost"),
        database=os.getenv("DB_NAME", "hospital"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "Neeltej@9"), # Defaulting to your original pass
        port=os.getenv("DB_PORT", "5432")
    )
    if db_pool:
        logger.info("Database connection pool created successfully.")
except (Exception, psycopg2.DatabaseError) as error:
    logger.error(f"Error while connecting to PostgreSQL: {error}")
    db_pool = None

def get_db_connection():
    """Fetches a connection from the pool."""
    if db_pool:
        return db_pool.getconn()
    raise Exception("Database connection pool is not initialized.")

def release_db_connection(conn):
    """Returns a connection to the pool."""
    if db_pool and conn:
        db_pool.putconn(conn)