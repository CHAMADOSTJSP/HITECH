# database.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Banco SQLite local
DATABASE_URL = "sqlite:///./voltguard.db"

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Modelo da Tabela de Painéis
class PanelModel(Base):
    __tablename__ = "panels"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    location = Column(String, nullable=False)
    voltage = Column(String, nullable=False)
    current = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    gateway_qr = Column(String, nullable=False)
    status = Column(String, default="NORMAL")
    component = Column(String, nullable=False)
    predictive_failure_hours = Column(Integer, nullable=False)
    recommendation = Column(String, nullable=True)
    esg_waste_kwh = Column(Float, default=0.0)
    assigned_to = Column(String, nullable=True)

# Modelo da Tabela de Logs de Auditoria
class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(String, nullable=False)
    user_name = Column(String, nullable=False)
    role = Column(String, nullable=False)
    action = Column(String, nullable=False)
    details = Column(String, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)