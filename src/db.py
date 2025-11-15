# Using MariaDB with SQLAlchemy, but you can use any
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
	Column,
	DateTime,
	Enum,
	Integer,
	MetaData,
	Numeric,
	String,
	Table,
	Text,
	create_engine,
	text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql import func


load_dotenv()

db_user = os.getenv("DB_USER")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")

missing = [
	name
	for name, value in {
		"DB_USER": db_user,
		"DB_PASSWORD": db_password,
		"DB_HOST": db_host,
		"DB_NAME": db_name,
	}.items()
	if not value
]

if missing:
	raise RuntimeError(
		"Missing required environment variables: " + ", ".join(missing)
	)


metadata = MetaData()

products_table = Table(
	"products",
	metadata,
	Column("id", Integer, primary_key=True, autoincrement=True),
	Column("name", String(255), nullable=False),
	Column("price_half_quantity", Numeric(10, 2), nullable=False),
)

conversations_table = Table(
	"conversations",
	metadata,
	Column("id", Integer, primary_key=True, autoincrement=True),
	Column("user_id", String(255), nullable=False),
	Column("role", Enum("user", "assistant", name="role_enum"), nullable=False),
	Column("content", Text, nullable=False),
	Column("created_at", DateTime, nullable=False, server_default=func.now()),
)


_engine: Optional[Engine] = None
SessionLocal = sessionmaker(autocommit=False, autoflush=False)


def _ensure_products_table_schema(engine: Engine) -> None:
	with engine.begin() as connection:
		try:
			result = connection.execute(text("SHOW TABLES LIKE 'products'"))
			if result.first() is None:
				return
			columns_result = connection.execute(text("SHOW COLUMNS FROM products"))
			columns = {row["Field"] for row in columns_result.mappings()}
			if "quantity_half_units" in columns:
				connection.execute(
					text("ALTER TABLE products DROP COLUMN quantity_half_units")
				)
				columns.remove("quantity_half_units")
			if "price" in columns and "price_half_quantity" not in columns:
				connection.execute(
					text(
						"ALTER TABLE products CHANGE COLUMN price "
						"price_half_quantity DECIMAL(10,2) NOT NULL"
					)
				)
		except SQLAlchemyError:
			pass


def ensure_database_exists() -> None:
	server_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/"
	server_engine = create_engine(server_url, isolation_level="AUTOCOMMIT")

	safe_db_name = db_name.replace("`", "``")
	with server_engine.connect() as connection:
		connection.execute(text(f"CREATE DATABASE IF NOT EXISTS `{safe_db_name}`"))

	server_engine.dispose()


def get_engine() -> Engine:
	global _engine
	if _engine is None:
		ensure_database_exists()
		engine_url = f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}"
		_engine = create_engine(engine_url, pool_pre_ping=True)
		metadata.create_all(_engine)
		SessionLocal.configure(bind=_engine)
		_ensure_products_table_schema(_engine)
	return _engine


def get_session() -> Session:
	get_engine()
	return SessionLocal()

