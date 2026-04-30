import json
import os

import boto3
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
_engine = None


def _get_db_url() -> str:
    env = os.getenv("APP_ENV", "local")
    if env == "local":
        host = os.getenv("LOCAL_DB_HOST", "localhost")
        port = os.getenv("LOCAL_DB_PORT", "5434")
        password = os.getenv("LOCAL_DB_PASSWORD", "localpassword")
        return f"postgresql://nextcart_admin:{password}@{host}:{port}/products"

    secret_arn = os.environ["DB_SECRET_ARN"]
    secret = json.loads(
        boto3.client("secretsmanager", region_name=os.environ["AWS_REGION_NAME"])
        .get_secret_value(SecretId=secret_arn)["SecretString"]
    )
    return (
        f"postgresql+psycopg2://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}?sslmode=require"
    )


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(_get_db_url(), pool_pre_ping=True, pool_size=3, max_overflow=0)
    return _engine


SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def get_db():
    db = SessionLocal(bind=get_engine())
    try:
        yield db
    finally:
        db.close()
