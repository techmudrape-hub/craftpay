"""
Database Configuration with Connection Pooling
Optimized for high-performance applications handling 1000+ requests per minute
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import scoped_session, sessionmaker

# Get database URL from environment
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Connection pooling configuration
# Adjust these values based on your RDS instance size and expected load
POOL_CONFIG = {
    # Core pool settings
    'pool_size': 20,              # Number of permanent connections in the pool
    'max_overflow': 40,           # Additional connections when pool is exhausted
    'pool_timeout': 30,           # Seconds to wait for a connection from pool
    'pool_recycle': 3600,         # Recycle connections after 1 hour (prevents stale connections)
    'pool_pre_ping': True,        # Verify connection health before using
    
    # Connection arguments for MySQL
    'connect_args': {
        'connect_timeout': 10,    # Connection timeout in seconds
        'keepalives': 1,          # Enable TCP keepalives
        'keepalives_idle': 30,    # Seconds before sending keepalive probe
        'keepalives_interval': 10, # Seconds between keepalive probes
        'keepalives_count': 5,    # Number of keepalive probes before giving up
    }
}

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=POOL_CONFIG['pool_size'],
    max_overflow=POOL_CONFIG['max_overflow'],
    pool_timeout=POOL_CONFIG['pool_timeout'],
    pool_recycle=POOL_CONFIG['pool_recycle'],
    pool_pre_ping=POOL_CONFIG['pool_pre_ping'],
    echo=False,  # Set to True for SQL query debugging
    connect_args=POOL_CONFIG['connect_args']
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create scoped session for thread-safe operations
db_session = scoped_session(SessionLocal)


def get_db():
    """
    Dependency function to get database session
    Use this in your routes to get a database session
    
    Example:
        @app.route('/api/transactions')
        def get_transactions():
            db = get_db()
            try:
                transactions = db.query(Transaction).all()
                return jsonify(transactions)
            finally:
                db.close()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_pool_status():
    """
    Get current connection pool status for monitoring
    Returns dict with pool statistics
    """
    pool = engine.pool
    return {
        'pool_size': pool.size(),
        'checked_in': pool.checkedin(),
        'checked_out': pool.checkedout(),
        'overflow': pool.overflow(),
        'total_connections': pool.size() + pool.overflow()
    }


def close_db_connection():
    """
    Close database connection
    Call this when shutting down the application
    """
    db_session.remove()
    engine.dispose()


# Flask-SQLAlchemy configuration (if using Flask-SQLAlchemy)
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': POOL_CONFIG['pool_size'],
    'max_overflow': POOL_CONFIG['max_overflow'],
    'pool_timeout': POOL_CONFIG['pool_timeout'],
    'pool_recycle': POOL_CONFIG['pool_recycle'],
    'pool_pre_ping': POOL_CONFIG['pool_pre_ping'],
}

# Configuration for different environments
POOL_CONFIGS = {
    'development': {
        'pool_size': 5,
        'max_overflow': 10,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    },
    'production': {
        'pool_size': 20,
        'max_overflow': 40,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    },
    'high_load': {
        'pool_size': 30,
        'max_overflow': 60,
        'pool_timeout': 30,
        'pool_recycle': 3600,
        'pool_pre_ping': True,
    }
}


def get_pool_config(environment='production'):
    """
    Get pool configuration for specific environment
    
    Args:
        environment: 'development', 'production', or 'high_load'
    
    Returns:
        dict: Pool configuration
    """
    return POOL_CONFIGS.get(environment, POOL_CONFIGS['production'])


# Example usage in Flask app
"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from database_config import SQLALCHEMY_ENGINE_OPTIONS, get_pool_status

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = SQLALCHEMY_ENGINE_OPTIONS
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

@app.route('/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        pool_status = get_pool_status()
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'pool_status': pool_status
        }), 200
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503

@app.route('/pool-status')
def pool_status():
    '''Endpoint to monitor connection pool status'''
    return jsonify(get_pool_status())
"""
