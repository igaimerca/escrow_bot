"""
Database models using SQLAlchemy
"""
from datetime import datetime
from sqlalchemy import (
    BigInteger, Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from config import DATABASE_URL

Base = declarative_base()
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(64))
    first_name = Column(String(128))
    is_banned = Column(Boolean, default=False)
    is_verified = Column(Boolean, default=False)
    referral_code = Column(String(16), unique=True)
    referred_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    joined_at = Column(DateTime, default=datetime.utcnow)
    deals_as_buyer = relationship("Deal", foreign_keys="Deal.buyer_id", back_populates="buyer")
    deals_as_seller = relationship("Deal", foreign_keys="Deal.seller_id", back_populates="seller")


class Deal(Base):
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True)
    transaction_id = Column(String(16), unique=True, nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default="USD")
    description = Column(Text)
    payment_method = Column(String(64))
    status = Column(String(32), default="pending")
    # Statuses: pending, waiting_payment, payment_submitted, funds_secured, in_progress, completed, cancelled, disputed
    payment_proof = Column(String(256))  # file_id of uploaded proof
    fee_amount = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    buyer = relationship("User", foreign_keys=[buyer_id], back_populates="deals_as_buyer")
    seller = relationship("User", foreign_keys=[seller_id], back_populates="deals_as_seller")
    dispute = relationship("Dispute", back_populates="deal", uselist=False)


class Dispute(Base):
    __tablename__ = "disputes"

    id = Column(Integer, primary_key=True)
    deal_id = Column(Integer, ForeignKey("deals.id"), nullable=False)
    opened_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text)
    evidence = Column(Text)  # comma-separated file_ids
    status = Column(String(32), default="open")  # open, resolved_buyer, resolved_seller, cancelled
    admin_notes = Column(Text)
    opened_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    deal = relationship("Deal", back_populates="dispute")
    opened_by = relationship("User")


class AdminLog(Base):
    __tablename__ = "admin_logs"

    id = Column(Integer, primary_key=True)
    admin_id = Column(BigInteger, nullable=False)
    action = Column(String(128))
    target_id = Column(BigInteger, nullable=True)
    notes = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(engine)
    print("✅ Database initialized.")


if __name__ == "__main__":
    init_db()
