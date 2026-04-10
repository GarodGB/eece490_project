from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from config import USE_MYSQL, SQLITE_DB_PATH, DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
from database.models import Base

if USE_MYSQL:
    import pymysql
    def _make_connection():
        return pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
        )
    engine = create_engine(
        "mysql+pymysql://",
        creator=_make_connection,
        echo=False,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
else:
    engine = create_engine(
        f"sqlite:///{SQLITE_DB_PATH}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

def init_db():
    
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] Dropped all existing tables")
        
        Base.metadata.create_all(bind=engine)
        print("[OK] Created all tables")
    except Exception as e:
        print(f"[ERROR] Database initialization failed: {e}")
        raise

def get_db():
    
    db = SessionLocal()
    try:
        return db
    finally:
        pass

def close_db():
    
    SessionLocal.remove()

def test_connection():
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            return True
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return False
