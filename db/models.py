from sqlalchemy import JSON, Column, Index, Integer, String, DateTime, ARRAY, UUID, Boolean, ForeignKey, Float, Text
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy import Column
from datetime import datetime
from db.database import engine
import uuid

Base = declarative_base()

class Incident(Base):
    """
    Base model class for incidents.

    Attributes:
        id (UUID): Primary key
        x_handle (str): X handle of the incident
        username (str): Username of the incident
        project_website (str): Website of the project
        affiliated_handles (list): List of affiliated handles
        scam_type (str): Type of scam
        updated_at (DateTime): Last updated timestamp

    """
    __tablename__ = "incidents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    x_handle = Column(String, nullable=False)
    username = Column(String, nullable=False)
    project_website = Column(String, nullable=False)
    affiliated_handles = Column(ARRAY(String), nullable=False)
    scam_type = Column(String, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))

    user = relationship("User", back_populates="incidents")

class DBTwitterUser(Base):
    __tablename__ = "twitter_users"
    
    id = Column(String, primary_key=True, unique=True)
    username = Column(String, unique=True, index=True)
    user_full_name = Column(String)
    user_description = Column(String)
    location = Column(String)
    website = Column(String)
    joined_at = Column(Integer)
    verified = Column(Boolean)
    total_tweets = Column(Integer)
    total_followers = Column(Integer)
    total_following = Column(Integer)
    profile_image_url = Column(String)
    profile_summary = Column(String)

    tweets = relationship("DBTweet", back_populates="user")
    analysis = relationship("ScamAnalysisResult", back_populates="twitter_user")
    ip_conflict_analysis = relationship("IpConflictAnalysis", back_populates="twitter_user")
    deep_research = relationship("DeepResearch", back_populates="twitter_user")
    token_risk_assessments = relationship("TokenRiskAssessment",back_populates="twitter_user")

class DBTweet(Base):
    __tablename__ = "tweets"

    id = Column(String, primary_key=True, unique=True)
    tweet_content = Column(String)
    posted_at = Column(Integer)
    is_retweet = Column(Boolean)
    retweeted_from = Column(String)
    username = Column(String, ForeignKey("twitter_users.username"))
    is_scam = Column(Boolean)
    scam_type = Column(String)
    scam_confidence_score = Column(Float)
    urls = Column(JSON, nullable=True)  # URLs found in the tweet in format {"url": "data"}
    mentioned_usernames = Column(JSON, nullable=True)  # Usernames mentioned in the tweet in format {"username": "data"}

    user = relationship("DBTwitterUser", back_populates="tweets")

class Runs(Base):
    __tablename__ = "runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    username = Column(String)
    status = Column(String) # Running, Completed
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    evaluation_type = Column(String)
    is_paid = Column(Boolean, default=False)
    transaction_id = Column(UUID(as_uuid=True), ForeignKey("transactions.id"), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    transaction = relationship("Transaction", back_populates="runs")
    user = relationship("User", back_populates="runs")
    deep_research = relationship("DeepResearch", back_populates="run")
    analysis = relationship("ScamAnalysisResult", back_populates="run")
    ip_conflict_analysis = relationship("IpConflictAnalysis", back_populates="run")
    token_risk_assessments = relationship("TokenRiskAssessment",back_populates="run")

class ScamAnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, ForeignKey("twitter_users.username"))
    token_risk = Column(JSON, nullable=True)
    profile_summary = Column(String)
    profile_analysis = Column(JSON)
    is_scammer = Column(Boolean)
    confidence_score = Column(Float)
    scam_types = Column(ARRAY(String))
    crypto_currencies = Column(ARRAY(String))
    risk_level = Column(String)
    risk_factors = Column(ARRAY(String))
    recommended_actions = Column(ARRAY(String))
    scam_evidences = Column(JSON)
    related_scam_profiles = Column(JSON)
    status = Column(String) # Running, Succeeded, Failed
    fail_reason = Column(String)
    analyzed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"))

    twitter_user = relationship("DBTwitterUser", back_populates="analysis")
    user = relationship("User", back_populates="analysis")
    run = relationship("Runs", back_populates="analysis")
    token_risk_assessments = relationship("TokenRiskAssessment",back_populates="analysis_result")

class IpConflictAnalysis(Base):
    __tablename__ = "ip_conflict_analysis"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, ForeignKey("twitter_users.username"))
    analysis = Column(JSON)
    status = Column(String)
    project_name = Column(String)
    project_description = Column(String)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"))

    twitter_user = relationship("DBTwitterUser", back_populates="ip_conflict_analysis")
    user = relationship("User", back_populates="ip_conflict_analysis")
    run = relationship("Runs", back_populates="ip_conflict_analysis")

class Limits(Base):
    __tablename__ = "limits"

    user_id = Column(UUID(as_uuid=True), primary_key=True)
    email = Column(String)
    eval_limit = Column(Integer)

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    stripe_customer_id = Column(String, nullable=True)
    auto_topup = Column(Boolean, default=False)
    auto_topup_amount = Column(Float, default=100.0)  # Default to $100
    
    wallet = relationship("Wallet", back_populates="user", uselist=False)
    transactions = relationship("Transaction", back_populates="user")
    incidents = relationship("Incident", back_populates="user")
    runs = relationship("Runs", back_populates="user")
    analysis = relationship("ScamAnalysisResult", back_populates="user")
    ip_conflict_analysis = relationship("IpConflictAnalysis", back_populates="user")
    redeemed_coupons = relationship("Coupon", back_populates="user")
    api_keys = relationship("APIKey", back_populates="user")
    deep_research = relationship("DeepResearch", back_populates="user")
    token_risk_assessments=relationship("TokenRiskAssessment",back_populates="user")


class Wallet(Base):
    __tablename__ = "wallets"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True)
    balance = Column(Float, default=0.0)  # Balance in USD
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="wallet")
    
class Transaction(Base):
    __tablename__ = "transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    stripe_payment_intent_id = Column(String, index=True, nullable=True)
    amount = Column(Float)  # Amount in USD
    status = Column(String)  # pending, completed, failed
    transaction_type = Column(String)  # subscription, topup, evaluation
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="transactions")
    runs = relationship("Runs", back_populates="transaction")

class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    key_hash = Column(String, nullable=False)
    name = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_api_key_hash', 'key_hash', postgresql_using='btree', unique=True),
    )
    user = relationship("User", back_populates="api_keys")

class Coupon(Base):
    __tablename__ = "coupons"
    
    id = Column(UUID(as_uuid=True), primary_key=True, index=True, default=uuid.uuid4)
    code = Column(String, unique=True, index=True)
    amount = Column(Float)  # Amount in USD
    is_redeemed = Column(Boolean, default=False)
    redeemed_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", foreign_keys=[redeemed_by], back_populates="redeemed_coupons")

class DeepResearch(Base):
    __tablename__ = "deep_research"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, ForeignKey("twitter_users.username"), index=True)
    research = Column(JSON)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"))

    twitter_user = relationship("DBTwitterUser", back_populates="deep_research")
    user = relationship("User", back_populates="deep_research")
    run = relationship("Runs", back_populates="deep_research")

class TokenRiskAssessment(Base):
    """
    Token risk assessment table for storing on-chain risk results.
    """
    __tablename__ = "token_risk_assessments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String, ForeignKey("twitter_users.username"), index=True)
    token_address = Column(String, nullable=True)
    token_symbol = Column(String, nullable=True)
    chain_id = Column(String, nullable=True)
    risk_report = Column(JSON, nullable=False) 
    risk_level = Column(String, nullable=False) 
    risk_score = Column(Float, nullable=False)  
    confidence_score = Column(Float, nullable=True)  
    status = Column(String, default="Succeeded")  
    fail_reason = Column(String, nullable=True)
    analyzed_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    run_id = Column(UUID(as_uuid=True), ForeignKey("runs.id"))
    analysis_result_id = Column(UUID(as_uuid=True), ForeignKey("analysis_results.id"), nullable=True)
    
    twitter_user = relationship("DBTwitterUser", back_populates="token_risk_assessments")
    user = relationship("User", back_populates="token_risk_assessments")
    run = relationship("Runs", back_populates="token_risk_assessments")
    analysis_result = relationship("ScamAnalysisResult", back_populates="token_risk_assessments")



class Summaries(Base):
    """
    Summaries table for pgvector-based similarity search
    """
    __tablename__ = "summaries"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    path = Column(Text, unique=True, nullable=False)
    username = Column(Text, nullable=False)
    user_id = Column(UUID(as_uuid=True), nullable=True)
    run_id = Column(UUID(as_uuid=True), nullable=True)
    document_type = Column(Text, nullable=True)
    timestamp = Column(DateTime, nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(Text, nullable=True)
    page_index = Column(Integer, nullable=True)
    embedding = Column(Vector(384))

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
