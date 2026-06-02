from fastapi import HTTPException
from configs.logfire_config import setup_logger
from db.models import APIKey, Coupon, DeepResearch, IpConflictAnalysis, ScamAnalysisResult, Incident, DBTwitterUser, DBTweet, Runs, Limits, User, Wallet, Transaction,TokenRiskAssessment
from schemas import IncidentCreate
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import UUID, desc, update
from sqlalchemy.exc import NoResultFound, IntegrityError, SQLAlchemyError
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union
import uuid
from db.database import get_db_context
from source.services.sparkpost import send_coupon
from source.services.stripe import StripeService
from source.utils.api_key import generate_api_key, generate_coupon_code, hash_api_key

logger = setup_logger(__name__)
stripe_service = StripeService()
evaluation_cost = 2.0
subscription_amount = 100.0  # $100 per subscription

## Incidents

def create_incident(incident: IncidentCreate, user_id: UUID):
    """
    Function to create an incident in the database

    Parameters:
    db: Session: SQLAlchemy session
    incident: IncidentCreate: IncidentCreate schema object

    Returns:
    db_incident: Incident: Incident object
    """
    with get_db_context() as db:
        try:
            logger.info("Creating new incident")
            db_incident = Incident(**incident.dict(), user_id=user_id)
            db.add(db_incident)
            db.commit()
            db.refresh(db_incident)
            return db_incident
        except Exception as e:
            logger.error(f"Error creating incident: {e}")
            db.rollback()
            return None

def get_incidents(user_id: UUID):
    """
    Function to get all incidents from the database

    Returns:
    db_incidents: List[Incident]: List of Incident objects
    """
    with get_db_context() as db:
        try:
            logger.info("Getting all incidents")
            return db.query(Incident).where(Incident.user_id == user_id).all()
        except Exception as e:
            logger.error(f"Error getting all incidents: {e}")
            return []

def get_incidents_by_username(username: str):
    """
    Function to get all incidents from the database

    Parameters:
    username: str: Username

    Returns:
    db_incidents: List[Incident]: List of Incident objects
    """
    with get_db_context() as db:
        try:
            logger.info("Getting all incidents")
            return db.query(Incident).filter(Incident.username == username).all()
        except Exception as e:
            logger.error(f"Error getting all incidents: {e}")
            return []


## Users

def upsert_user(user_data: Dict) -> Dict:
    """
    Upserts a user entry into the twitter_users table.
    
    Args:
        db (Session): SQLAlchemy session object
        user_data (Dict): Dictionary containing user data
    """
    with get_db_context() as db:
        stmt = insert(DBTwitterUser).values(
            id=user_data['user_id'],
            username=user_data['username'],
            user_full_name=user_data['name'],
            user_description=user_data['description'],
            location=user_data['location'],
            website=user_data['external_url'],
            joined_at=user_data['timestamp'],
            verified=user_data['is_verified'],
            total_tweets=user_data['number_of_tweets'],
            total_followers=user_data['follower_count'],
            total_following=user_data['following_count'],
            profile_image_url=user_data['profile_pic_url'],
            profile_summary="",
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[DBTwitterUser.username],
            set_={
                # 'id': stmt.excluded.id,
                'user_full_name': stmt.excluded.user_full_name,
                'user_description': stmt.excluded.user_description,
                'location': stmt.excluded.location,
                'website': stmt.excluded.website,
                'joined_at': stmt.excluded.joined_at,
                'verified': stmt.excluded.verified,
                'total_tweets': stmt.excluded.total_tweets,
                'total_followers': stmt.excluded.total_followers,
                'total_following': stmt.excluded.total_following,
                'profile_image_url': stmt.excluded.profile_image_url,
                'profile_summary': stmt.excluded.profile_summary,
            }
        )
        
        db.execute(stmt)
        db.commit()
        return {
            'status': 'success',
            'message': 'Successfully upserted user',
            'username': user_data['username']
        }

def delete_user(username: str):
    with get_db_context() as db:
        db.query(DBTwitterUser).filter(DBTwitterUser.username == username).delete()
        db.commit()
        return {
            'status': 'success',
            'message': 'Successfully deleted user',
            'username': username
        }

def fetch_profile_summary_and_ip_conflict(username: str) -> Tuple[str, dict]:
    with get_db_context() as db:
        user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
        return user.profile_summary, user.ip_conflict_analysis

def fetch_profile_summary(username: str) -> Optional[str]:
    with get_db_context() as db:
        user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
        return user.profile_summary

def upsert_profile_summary_and_ip_conflict(username: str, summary: str, ip_conflict: dict) -> Dict:
    with get_db_context() as db:
        user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
        user.profile_summary = summary
        user.ip_conflict_analysis = ip_conflict
        db.commit()
        return {
            'status': 'success',
            'message': 'Successfully upserted profile summary',
            'username': username
        }

def upsert_profile_summary(username: str, summary: str) -> Dict:
    try:
        with get_db_context() as db:
            user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
            if user is None:
                logger.warning(f"User {username} not found in database when updating profile summary")
                # Try to create a minimal user record
                try:
                    minimal_user = {
                        'username': username, 
                        'user_id': int(datetime.now().timestamp()),
                        'profile_summary': summary
                    }
                    logger.info(f"Creating minimal user for {username} to store profile summary")
                    return upsert_user(minimal_user)
                except Exception as create_e:
                    logger.error(f"Failed to create minimal user: {str(create_e)}")
                    return {
                        'status': 'error',
                        'message': f'User {username} not found and could not be created',
                        'username': username,
                        'error': str(create_e)
                    }
            
            user.profile_summary = summary
            db.commit()
            logger.info(f"Successfully upserted profile summary for {username}")
            return {
                'status': 'success',
                'message': 'Successfully upserted profile summary',
                'username': username
            }
    except Exception as e:
        logger.error(f"Error in upsert_profile_summary for {username}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error updating profile summary: {str(e)}',
            'username': username,
            'error': str(e)
        }

## Tweets

def upsert_tweets(tweets_data: List[Dict], input_username: str) -> Dict:
    """
    Performs an optimized bulk upsert operation for tweets with deduplication.
    
    Args:
        tweets_data: List of tweet dictionaries
        input_username: Username to use for non-retweet tweets
        
    Returns:
        Dict with status, message and processed count
    """
    with get_db_context() as session:
        processed_count = 0
        seen_ids = set()
        values = []
        
        # Process and deduplicate tweets
        for tweet in tweets_data:
            # Handle both old format ('text') and new format ('tweet_content')
            tweet_content = tweet.get('tweet_content') or tweet.get('text')
            if not tweet_content:
                continue
                
            tweet_id = tweet.get('id')
            if not tweet_id or tweet_id in seen_ids:
                continue
                
            seen_ids.add(tweet_id)
            values.append({
                'id': tweet_id,
                'tweet_content': tweet_content,
                'is_retweet': tweet['is_retweet'],
                'retweeted_from': tweet['retweeted_from'],
                'posted_at': tweet['posted_at'],
                'username': input_username,
                'is_scam': tweet.get('is_scam', False),
                'scam_type': tweet.get('scam_type', None),
                'scam_confidence_score': tweet.get('scam_confidence_score', 0.0),
                'urls': tweet.get('urls', []),
                'mentioned_usernames': tweet.get('mentioned_usernames', []),
            })
        
        if values:
            try:
                # Process in batches of 100
                batch_size = 100
                for i in range(0, len(values), batch_size):
                    batch = values[i:i + batch_size]
                    stmt = insert(DBTweet).values(batch)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=[DBTweet.id],
                        set_={
                            'tweet_content': stmt.excluded.tweet_content,
                            'is_retweet': stmt.excluded.is_retweet,
                            'retweeted_from': stmt.excluded.retweeted_from,
                            'posted_at': stmt.excluded.posted_at,
                            'username': stmt.excluded.username,
                            'is_scam': stmt.excluded.is_scam,
                            'scam_type': stmt.excluded.scam_type,
                            'scam_confidence_score': stmt.excluded.scam_confidence_score,
                            'urls': stmt.excluded.urls,
                            'mentioned_usernames': stmt.excluded.mentioned_usernames
                        }
                    )
                    session.execute(stmt)
                    session.commit()
                    
                processed_count = len(values)
                return {
                    'status': 'success',
                    'message': f'Successfully processed {processed_count} tweets',
                    'processed_count': processed_count
                }
                
            except Exception as e:
                session.rollback()
                return {
                    'status': 'error',
                    'message': f'Error processing tweets: {str(e)}',
                    'processed_count': 0
                }
        
        return {
            'status': 'success',
            'message': 'No tweets to process',
            'processed_count': 0
        }

def get_all_tweets_and_retweets(username: str) -> Tuple[List[Dict], List[Dict]]:
    with get_db_context() as db:
        all_tweets = db.query(DBTweet).filter(DBTweet.username == username).all()
        if not all_tweets:
            return [], []
        tweets, retweets = [], []
        for tweet in all_tweets:
            tweet_data = {
                'id': tweet.id,
                'tweet_content': tweet.tweet_content,
                'is_retweet': tweet.is_retweet,
                'retweeted_from': tweet.retweeted_from,
                'posted_at': tweet.posted_at,
                'username': tweet.username,
                'urls': tweet.urls if tweet.urls else {},
                'mentioned_usernames': tweet.mentioned_usernames if tweet.mentioned_usernames else {}
            }
            if tweet.is_retweet:
                retweets.append(tweet_data)
            else:
                tweets.append(tweet_data)
        return tweets, retweets

def get_latest_tweet(username: str) -> Optional[Dict]:
    """
    Retrieves the latest tweet for a username.
    """
    with get_db_context() as db:
        user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
        
        if not user:
            return None
            
        tweet = db.query(DBTweet)\
            .filter(DBTweet.username == username)\
            .order_by(desc(DBTweet.posted_at))\
            .first()
        
        if not tweet:
            return None
        
        return {
                'content': tweet.tweet_content,
                'is_retweet': tweet.is_retweet,
                'retweeted_from': tweet.retweeted_from,
                'posted_at': tweet.posted_at,
                'username': tweet.username,
                'urls': tweet.urls if tweet.urls else {},
                'mentioned_usernames': tweet.mentioned_usernames if tweet.mentioned_usernames else {}
            }

def get_top_tweets_by_scam_type(usernames: List[str], scam_types: List[str]) -> Dict:
    """
    Get top 5 tweets for each scam type for each username, sorted by confidence score.
    
    Args:
        usernames: List of usernames to query
        scam_types: List of scam types to filter
        
    Returns:
        Dict with structure:
        {
            'username1': {
                'scam_type1': [
                    {
                        'id': str,
                        'tweet_content': str,
                        'posted_at': int,
                        'scam_confidence_score': float,
                        'urls': Dict[str, str],
                        'mentioned_usernames': Dict[str, Dict]
                    },
                    ...
                ],
                'scam_type2': [...],
            },
            'username2': {...}
        }
    """
    result = {}
    
    with get_db_context() as db:
        for username in usernames:
            latest_entry = db.query(ScamAnalysisResult).filter(
                ScamAnalysisResult.username == username
            ).order_by(ScamAnalysisResult.analyzed_at.desc()).first()
            
            if not latest_entry or not latest_entry.is_scammer:
                continue
            
            result[username] = {}
            
            for scam_type in scam_types:
                top_tweets = (
                    db.query(
                        DBTweet.id,
                        DBTweet.tweet_content,
                        DBTweet.posted_at,
                        DBTweet.scam_confidence_score,
                        DBTweet.urls,
                        DBTweet.mentioned_usernames
                    )
                    .filter(
                        DBTweet.username == username,
                        DBTweet.scam_type == scam_type,
                        DBTweet.is_scam == True
                    )
                    .order_by(DBTweet.scam_confidence_score.desc())
                    .limit(5)
                    .all()
                )
                
                result[username][scam_type] = [
                    {
                        'id': tweet.id,
                        'tweet_content': tweet.tweet_content,
                        'posted_at': tweet.posted_at,
                        'scam_confidence_score': tweet.scam_confidence_score,
                        'urls': tweet.urls if tweet.urls else {},
                        'mentioned_usernames': tweet.mentioned_usernames if tweet.mentioned_usernames else {}
                    }
                    for tweet in top_tweets
                ]
    
    return result

def get_tweets_by_scam_type(username: str, scam_types: str) -> List[Dict]:
    result = {}
    with get_db_context() as db:
        for scam_type in scam_types:
            top_tweets = (
                    db.query(
                        DBTweet.tweet_content,
                        DBTweet.urls,
                        DBTweet.mentioned_usernames
                    )
                    .filter(
                        DBTweet.username == username,
                        DBTweet.scam_type == scam_type,
                        DBTweet.is_scam == True
                    )
                    .order_by(DBTweet.scam_confidence_score.desc())
                    .limit(5)
                    .all()
                )

            result[scam_type] = [
                {
                    'tweet_content': tweet.tweet_content,
                    'urls': tweet.urls if tweet.urls else {},
                    'mentioned_usernames': tweet.mentioned_usernames if tweet.mentioned_usernames else {}
                } for tweet in top_tweets
            ]

    return result


## IP Conflict

def get_latest_ip_conflict_analysis(
    username: str,
    project_name: str,
    project_description: str
) -> Optional[IpConflictAnalysis]:
    """Fetch the latest analysis entry for given parameters."""
    with get_db_context() as db:
        return (
            db.query(IpConflictAnalysis)
            .filter(
                IpConflictAnalysis.username == username,
                IpConflictAnalysis.project_name == project_name,
                IpConflictAnalysis.project_description == project_description
            )
            .order_by(desc(IpConflictAnalysis.updated_at))
            .first()
        )

def get_unique_analyses_for_username(
    username: str
) -> List[IpConflictAnalysis]:
    """Fetch all unique analyses for a given username."""
    with get_db_context() as db:
        analyses = db.query(IpConflictAnalysis).filter(IpConflictAnalysis.username == username).distinct(
                IpConflictAnalysis.project_name,
                IpConflictAnalysis.project_description
            ).order_by(
                IpConflictAnalysis.project_name,
                IpConflictAnalysis.project_description,
                desc(IpConflictAnalysis.updated_at)
            ).all()

        all_analyses = [{"analysis" : analysis.analysis,
                         "project" : analysis.project_name,
                         "description" : analysis.project_description}  for analysis in analyses]
        return all_analyses

def upsert_ip_conflict_analysis(
    username: str,
    project_name: str,
    project_description: str,
    user_id: UUID,
    run_id: UUID = None,
    analysis_data: dict = None,
    status: str = "PENDING"
) -> IpConflictAnalysis:
    """
    Create a new IP conflict analysis entry.
    Always creates a new entry regardless of existing entries.
    
    Args:
        username: Twitter username
        project_name: Name of the project
        project_description: Description of the project
        user_id: UUID of the user
        run_id: UUID of the associated run
        analysis_data: Dictionary containing analysis results (optional)
        status: Status of the analysis (default: "PENDING")
    
    Returns:
        IpConflictAnalysis: Created analysis entry
    """
    with get_db_context() as db:
        # Create new entry
        new_analysis = IpConflictAnalysis(
            id=uuid.uuid4(),
            username=username,
            project_name=project_name,
            project_description=project_description,
            user_id=user_id,
            run_id=run_id,
            status=status,
            analysis=analysis_data
        )
        db.add(new_analysis)
        db.commit()
        return new_analysis



def create_token_risk_assessment(
    username: str,
    user_id: UUID,
    run_id: UUID,
    analysis_result_id: UUID,
    token_address: str,
    token_symbol: Optional[str],
    chain_id: Optional[str],
    risk_report: dict,
    risk_level: str,
    risk_score: float,
    confidence_score: Optional[float] = None,
    status: str = "Succeeded",
    fail_reason: Optional[str] = None,
):
    with get_db_context() as db:
        tra = TokenRiskAssessment(
            username=username,
            user_id=user_id,
            run_id=run_id,
            analysis_result_id=analysis_result_id,
            token_address=token_address,
            token_symbol=token_symbol,
            chain_id=chain_id,
            risk_report=risk_report,
            risk_level=risk_level,
            risk_score=risk_score,
            confidence_score=confidence_score,
            status=status,
            fail_reason=fail_reason,
        )
        db.add(tra)
        db.commit()
        db.refresh(tra)
        return tra



def update_token_risk_assessment_status(tra_id: UUID, status: str, fail_reason: Optional[str] = None):
    with get_db_context() as db:
        tra = db.query(TokenRiskAssessment).filter(TokenRiskAssessment.id == tra_id).first()
        if not tra:
            return None
        tra.status = status
        tra.fail_reason = fail_reason
        db.commit()
        db.refresh(tra)
        return tra

def get_token_risk_assessments(username: str, user_id: UUID):
    with get_db_context() as db:
        rows = (
            db.query(TokenRiskAssessment)
            .filter(TokenRiskAssessment.username == username, TokenRiskAssessment.user_id == user_id)
            .order_by(TokenRiskAssessment.analyzed_at.desc())
            .all()
        )
        return [
            {
                "id": str(r.id),
                "username": r.username,
                "token_address": r.token_address,
                "token_symbol": r.token_symbol,
                "chain_id": r.chain_id,
                "risk_level": r.risk_level,
                "risk_score": r.risk_score,
                "confidence_score": r.confidence_score,
                "status": r.status,
                "fail_reason": r.fail_reason,
                "risk_report": r.risk_report,
                "run_id": str(r.run_id) if r.run_id else None,
                "analysis_result_id": str(r.analysis_result_id) if r.analysis_result_id else None,
                "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
            }
            for r in rows
        ]

## Analysis

def create_analysis_entry(username: str, user_id: UUID, run_id: UUID = None) -> Dict:
    """
    Creates a new analysis entry or updates existing one with 'Running' status.
    
    Args:
        username: Twitter username
        user_id: UUID of the user
        run_id: UUID of the associated run
    
    Returns:
        Dict with created or updated analysis entry details
    """
    with get_db_context() as db:
        existing_entry = db.query(ScamAnalysisResult).filter(
            ScamAnalysisResult.username == username,
            ScamAnalysisResult.user_id == user_id
        ).first()
        
        if existing_entry:
            existing_entry.status = 'Running'
            existing_entry.analyzed_at = datetime.utcnow()
            if run_id:
                existing_entry.run_id = run_id
            db.commit()
            result = existing_entry
        else:
            stmt = insert(ScamAnalysisResult).values(
                id=uuid.uuid4(),
                username=username,
                status='Running',
                user_id=user_id,
                run_id=run_id
            ).returning(ScamAnalysisResult)
            result = db.execute(stmt).scalar_one()
            db.commit()
        
        return {
            'id': str(result.id),
            'username': result.username,
            'status': result.status,
            'analyzed_at': result.analyzed_at.isoformat()
        }

def create_analysis_entry_new(username: str, user_id: UUID, run_id: UUID = None) -> Dict:
    """
    Creates a new analysis entry with 'Running' status.
    
    Args:
        username: Twitter username
        user_id: UUID of the user
        run_id: UUID of the associated run
    
    Returns:
        Dict with created analysis entry details
    """
    with get_db_context() as db:
        stmt = insert(ScamAnalysisResult).values(
            id=uuid.uuid4(),
            username=username,
            status='Running',
            user_id=user_id,
            run_id=run_id
        ).returning(ScamAnalysisResult)
        result = db.execute(stmt).scalar_one()
        db.commit()
        
        return {
            'id': str(result.id),
            'username': result.username,
            'status': result.status,
            'analyzed_at': result.analyzed_at.isoformat()
        }

def update_analysis_result_new(
    entry_id: UUID,
    status: str,
    profile_summary: str = None,
    profile_analysis: dict = None,
    is_scammer: bool = None,
    confidence_score: float = None,
    scam_types: list = None,
    crypto_currencies: list = None,
    risk_level: str = None,
    risk_factors: list = None,
    recommended_actions: list = None,
    scam_evidences: dict = None,
    related_scam_profiles: dict = None,
    fail_reason: str = None,
    token_risk: dict = None
) -> Dict:
    """
    Updates analysis result with success/failure status and data.
    """
    with get_db_context() as db:
        update_values = {
            'status': status,
            'analyzed_at': datetime.utcnow()
        }
        
        if status == 'Succeeded':
            update_values.update({
                'profile_summary': profile_summary,
                'profile_analysis': profile_analysis,
                'is_scammer': is_scammer,
                'confidence_score': confidence_score,
                'scam_types': scam_types,
                'crypto_currencies': crypto_currencies,
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'recommended_actions': recommended_actions,
                'scam_evidences': scam_evidences,
                'related_scam_profiles': related_scam_profiles,
                'token_risk': token_risk,
                'fail_reason': None
            })
        else:
            update_values.update({
                'fail_reason': fail_reason
            })
        
        stmt = (
            db.query(ScamAnalysisResult)
            .filter(ScamAnalysisResult.id == entry_id)
            .first()
        )
        
        if not stmt:
            return None
            
        for key, value in update_values.items():
            setattr(stmt, key, value)
        
        db.commit()
        
        return {
            'id': str(stmt.id),
            'username': stmt.username,
            'user_id': str(stmt.user_id),
            'profile_summary': stmt.profile_summary,
            'profile_analysis': stmt.profile_analysis,
            'status': stmt.status,
            'is_scammer': stmt.is_scammer,
            'confidence_score': stmt.confidence_score,
            'scam_types': stmt.scam_types,
            'crypto_currencies': stmt.crypto_currencies,
            'risk_level': stmt.risk_level,
            'risk_factors': stmt.risk_factors,
            'recommended_actions': stmt.recommended_actions,
            'scam_evidences': stmt.scam_evidences,
            'related_scam_profiles': stmt.related_scam_profiles,
            'token_risk': stmt.token_risk,
            'analyzed_at': stmt.analyzed_at.isoformat(),
            'fail_reason': stmt.fail_reason
        }

def update_analysis_result(
    username: str,
    user_id: UUID,
    status: str,
    profile_summary: str = None,
    profile_analysis: dict = None,
    is_scammer: bool = None,
    confidence_score: float = None,
    scam_types: list = None,
    crypto_currencies: list = None,
    risk_level: str = None,
    risk_factors: list = None,
    recommended_actions: list = None,
    scam_evidences: dict = None,
    related_scam_profiles: dict = None,
    fail_reason: str = None
) -> Dict:
    """
    Updates analysis result with success/failure status and data.
    """
    with get_db_context() as db:
        update_values = {
            'status': status,
            'analyzed_at': datetime.utcnow()
        }
        
        if status == 'Succeeded':
            update_values.update({
                'profile_summary': profile_summary,
                'profile_analysis': profile_analysis,
                'is_scammer': is_scammer,
                'confidence_score': confidence_score,
                'scam_types': scam_types,
                'crypto_currencies': crypto_currencies,
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'recommended_actions': recommended_actions,
                'scam_evidences': scam_evidences,
                'related_scam_profiles': related_scam_profiles,
                'fail_reason': None
            })
        else:
            update_values.update({
                'fail_reason': fail_reason
            })
        
        stmt = (
            db.query(ScamAnalysisResult)
            .filter(ScamAnalysisResult.username == username, ScamAnalysisResult.user_id == user_id)
            .order_by(ScamAnalysisResult.analyzed_at.desc())
            .first()
        )
        
        if not stmt:
            return None
            
        for key, value in update_values.items():
            setattr(stmt, key, value)
        
        db.commit()
        
        return {
            'id': str(stmt.id),
            'username': stmt.username,
            'user_id': str(stmt.user_id),
            'profile_summary': stmt.profile_summary,
            'profile_analysis': stmt.profile_analysis,
            'status': stmt.status,
            'is_scammer': stmt.is_scammer,
            'confidence_score': stmt.confidence_score,
            'scam_types': stmt.scam_types,
            'crypto_currencies': stmt.crypto_currencies,
            'risk_level': stmt.risk_level,
            'risk_factors': stmt.risk_factors,
            'recommended_actions': stmt.recommended_actions,
            'scam_evidences': stmt.scam_evidences,
            'related_scam_profiles': stmt.related_scam_profiles,
            'analyzed_at': stmt.analyzed_at.isoformat(),
            'fail_reason': stmt.fail_reason
        }

def get_analysis_results(username: str, user_id: UUID) -> Optional[Dict]:
    """
    Retrieves the latest analysis status for a username.
    """
    with get_db_context() as db:
        result = (
            db.query(ScamAnalysisResult)
            .filter(ScamAnalysisResult.username == username, ScamAnalysisResult.user_id == user_id)
            .order_by(ScamAnalysisResult.analyzed_at.desc())
            .first()
        )
        
        if not result:
            return None
        
        # Get token_risk: prioritize the one linked to this specific analysis_result_id
        token_risk_payload = None
        
        # First, try to get token_risk from token_risk_assessments table linked to this analysis_result_id
        tra = (
            db.query(TokenRiskAssessment)
            .filter(TokenRiskAssessment.analysis_result_id == result.id)
            .order_by(TokenRiskAssessment.analyzed_at.desc())
            .first()
        )
        
        if tra:
            # Use the assessment linked to this analysis_result_id
            token_risk_payload = {
                "id": str(tra.id),
                "token_address": tra.token_address,
                "token_symbol": tra.token_symbol,
                "chain_id": tra.chain_id,
                "risk_level": tra.risk_level,
                "risk_score": tra.risk_score,
                "confidence_score": tra.confidence_score,
                "status": tra.status,
                "fail_reason": tra.fail_reason,
                "risk_report": tra.risk_report,
                "run_id": str(tra.run_id) if tra.run_id else None,
                "analysis_result_id": str(tra.analysis_result_id) if tra.analysis_result_id else None,
                "analyzed_at": tra.analyzed_at.isoformat() if tra.analyzed_at else None,
            }
        elif result.token_risk:
            # Fallback to JSON column if no linked assessment found
            # Verify the JSON has an id and matches this analysis_result_id
            json_token_risk = result.token_risk
            json_analysis_result_id = json_token_risk.get("analysis_result_id") if isinstance(json_token_risk, dict) else None
            
            # Only use JSON if it's linked to this analysis_result_id or has no analysis_result_id (legacy data)
            if not json_analysis_result_id or str(json_analysis_result_id) == str(result.id):
                token_risk_payload = json_token_risk
                # Ensure id exists in the payload
                if isinstance(token_risk_payload, dict) and "id" not in token_risk_payload:
                    # Try to find the matching assessment by other fields
                    if "token_address" in token_risk_payload:
                        matching_tra = (
                            db.query(TokenRiskAssessment)
                            .filter(
                                TokenRiskAssessment.username == username,
                                TokenRiskAssessment.user_id == user_id,
                                TokenRiskAssessment.token_address == token_risk_payload.get("token_address")
                            )
                            .order_by(TokenRiskAssessment.analyzed_at.desc())
                            .first()
                        )
                        if matching_tra and matching_tra.analysis_result_id == result.id:
                            token_risk_payload["id"] = str(matching_tra.id)
                            token_risk_payload["analysis_result_id"] = str(result.id)
        
        # If still no token_risk found, try fallback to latest assessment for username/user_id
        if not token_risk_payload:
            tra_fallback = (
                db.query(TokenRiskAssessment)
                .filter(
                    TokenRiskAssessment.username == username,
                    TokenRiskAssessment.user_id == user_id,
                )
                .order_by(TokenRiskAssessment.analyzed_at.desc())
                .first()
            )
            if tra_fallback:
                token_risk_payload = {
                    "id": str(tra_fallback.id),
                    "token_address": tra_fallback.token_address,
                    "token_symbol": tra_fallback.token_symbol,
                    "chain_id": tra_fallback.chain_id,
                    "risk_level": tra_fallback.risk_level,
                    "risk_score": tra_fallback.risk_score,
                    "confidence_score": tra_fallback.confidence_score,
                    "status": tra_fallback.status,
                    "fail_reason": tra_fallback.fail_reason,
                    "risk_report": tra_fallback.risk_report,
                    "run_id": str(tra_fallback.run_id) if tra_fallback.run_id else None,
                    "analysis_result_id": str(tra_fallback.analysis_result_id) if tra_fallback.analysis_result_id else None,
                    "analyzed_at": tra_fallback.analyzed_at.isoformat() if tra_fallback.analyzed_at else None,
                }
        
        return {
            'id': str(result.id),
            'username': result.username,
            'user_id': str(result.user_id),
            'profile_summary': result.profile_summary,
            'profile_analysis': result.profile_analysis,
            'status': result.status,
            'is_scammer': result.is_scammer,
            'confidence_score': result.confidence_score,
            'scam_types': result.scam_types,
            'crypto_currencies': result.crypto_currencies,
            'risk_level': result.risk_level,
            'risk_factors': result.risk_factors,
            'recommended_actions': result.recommended_actions,
            'scam_evidences': result.scam_evidences,
            'related_scam_profiles': result.related_scam_profiles,
            'fail_reason': result.fail_reason,
            'analyzed_at': result.analyzed_at.isoformat(),
            'token_risk': token_risk_payload
        }

def get_latest_analysis_results_for_username(username: str) -> Optional[Dict]:
    """
    Retrieves the latest analysis status for a username.
    """
    with get_db_context() as db:
        result = (
            db.query(ScamAnalysisResult)
            .filter(ScamAnalysisResult.username == username)
            .order_by(ScamAnalysisResult.analyzed_at.desc())
            .first()
        )
        
        if not result:
            return None
            
        return {
            'id': str(result.id),
            'username': result.username,
            'user_id': result.user_id,
            'profile_summary': result.profile_summary,
            'profile_analysis': result.profile_analysis,
            'status': result.status,
            'is_scammer': result.is_scammer,
            'confidence_score': result.confidence_score,
            'scam_types': result.scam_types,
            'crypto_currencies': result.crypto_currencies,
            'risk_level': result.risk_level,
            'risk_factors': result.risk_factors,
            'recommended_actions': result.recommended_actions,
            'scam_evidences': result.scam_evidences,
            'related_scam_profiles': result.related_scam_profiles,
            'fail_reason': result.fail_reason,
            'analyzed_at': result.analyzed_at.isoformat()
        }

## Runs

def create_run_entry(user_id: str, username: str, transaction_id: str, evaluation_type: str) -> Dict:
    """
    Creates a new run entry.

    Args:
        user_id (str): The user ID.
        username (str): The username.
    
    Returns:
        Dict: The created run entry.
    """
    with get_db_context() as db:
        stmt = insert(Runs).values(
            id=uuid.uuid4(),
            user_id=user_id,
            username=username,
            status='Running',
            is_paid=True,
            transaction_id=transaction_id,
            evaluation_type=evaluation_type
        ).returning(Runs)
        result = db.execute(stmt).scalar_one()
        db.commit()
        
        return {
            'id': str(result.id),
            'user_id': str(result.user_id),
            'username': result.username,
            'status': result.status,
            'is_paid': result.is_paid,
            'transaction_id': str(result.transaction_id),
            'updated_at': result.updated_at.isoformat()
        }

def complete_run_entry(run_id: str, input_tokens: int, output_tokens: int) -> Dict:
    """
    Updates a run entry.

    Args:
        run_id (str): The run ID.
    
    Returns:
        Dict: The updated run entry.
    """
    with get_db_context() as db:
        stmt = update(Runs).where(Runs.id == run_id).values(status='Completed', input_tokens=input_tokens, output_tokens=output_tokens)
        db.execute(stmt)
        db.commit()
        
        return {
            'id': run_id,
            'status': 'Completed'
        }

def get_runs(user_id: UUID) -> List[Dict]:
    """
    Retrieves all runs for a user.

    Args:
        user_id (UUID): The user ID.
    
    Returns:
        List[Dict]: The list of scam analysis results for the user.
    """
    with get_db_context() as db:
        try:
            results = db.query(Runs).filter(Runs.user_id == user_id).order_by(Runs.updated_at.desc()).all()
            return results
        except Exception as e:
            logger.error(f"Error getting all runs: {e}")
            return []

def get_running_run_for_username(username: str, user_id: UUID) -> Optional[Dict]:
    """
    Retrieves a running run for a username.

    Args:
        username (str): The username.

    Returns:
        Optional[Dict]: The running run for the username if exists, else None.
    """
    with get_db_context() as db:
        try:
            result = db.query(Runs).filter(Runs.username == username, Runs.user_id == user_id, Runs.status == 'Running').first()
            return result
        except Exception as e:
            logger.error(f"Error getting running run for username: {e}")
            return None

## Limits

def create_limit_entry(user_id: str, email: str):
    """
    Creates a new limit entry.

    Args:
        user_id (str): The user ID.
        email (str): The email.
    
    Returns:
        The created limit entry.
    """
    with get_db_context() as db:
        stmt = insert(Limits).values(
            user_id=user_id,
            eval_limit=10,
            email=email
        ).returning(Limits)
        result = db.execute(stmt).scalar_one()
        db.commit()
        
        return result

def get_limit_entry(user_id: UUID) -> Optional[int]:
    """
    Retrieves a limit entry for a user.

    Args:
        user_id (UUID): The user ID.

    Returns:
        The Evaluation limit for the user.
    """
    with get_db_context() as db:
        try:
            result = db.query(Limits).filter(Limits.user_id == user_id).first()
            return result.eval_limit
        except Exception as e:
            logger.error(f"Error getting limit entry for user: {e}")
            return None

def reduce_limit_entry(user_id: UUID):
    """
    Reduces the limit entry for a user.

    Args:
        user_id (UUID): The user ID.
    
    Returns:
        The updated limit entry.
    """
    with get_db_context() as db:
        try:
            stmt = update(Limits).where(Limits.user_id == user_id).values(eval_limit=Limits.eval_limit - 1)
            db.execute(stmt)
            db.commit()
            result = db.query(Limits).filter(Limits.user_id == user_id).first()
            return result
        except Exception as e:
            logger.error(f"Error reducing limit entry for user: {e}")
            return None

def get_all_limit_entries() -> List[Dict[str, Union[str, int]]]:
    """
    Retrieves all limit entries.

    Returns:
        List[Dict[str, Union[str, int]]]: The list of limit entries.
    """
    with get_db_context() as db:
        try:
            results = db.query(Limits.email, Limits.eval_limit).all()
            return [{"email": result[0], "eval_limit": result[1]} for result in results]
        except Exception as e:
            logger.error(f"Error getting all limit entries: {e}")
            return []

def update_limit_entry(email: str, eval_limit: int):
    """
    Updates a limit entry for a user.

    Args:
        email (str): The email.
        eval_limit (int): The evaluation limit.

    Returns:
        The updated limit entry.
    """
    with get_db_context() as db:
        try:
            existing_entry = db.query(Limits).filter(Limits.email == email).first()
            if not existing_entry:
                raise HTTPException(
                    status_code=400,
                    detail="Email does not exist, cannot update limit entry"
                )
            stmt = update(Limits).where(Limits.email == email).values(eval_limit=eval_limit)
            db.execute(stmt)
            db.commit()
            result = db.query(Limits).filter(Limits.email == email).first()
            return result
        except HTTPException as e:
            logger.error(e.detail)
            raise HTTPException(
                status_code=e.status_code,
                detail=e.detail
            )
        except Exception as e:
            logger.error(f"Error updating limit entry for user: {e}")
            return None

## User

def create_user(id: UUID, email: str) -> Dict:
    with get_db_context() as db:
        try:
            user = db.query(User).filter(User.id == id).first()
            if user:
                logger.info(f"User already exists: {user}")
                return user
            else:
                user = User(id=id, email=email)
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"User created: {user}")
                return user
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

def get_user_details(user_id: UUID) -> Optional[User]:
    with get_db_context() as db:
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error("User not found")
                raise ValueError("User not found")
            return user
        except ValueError as e:
            logger.error(f"Error getting user: {e}")
            return None

def delete_all_data_for_user(user_id: UUID):
    with get_db_context() as db:
        try:
            # Delete in order of dependencies to avoid foreign key constraint violations
            
            # First delete records from tables that depend on other tables
            db.query(Transaction).filter(Transaction.user_id == user_id).delete()
            db.query(Runs).filter(Runs.user_id == user_id).delete()
            db.query(Incident).filter(Incident.user_id == user_id).delete()
            db.query(ScamAnalysisResult).filter(ScamAnalysisResult.user_id == user_id).delete()
            db.query(IpConflictAnalysis).filter(IpConflictAnalysis.user_id == user_id).delete()
            db.query(DeepResearch).filter(DeepResearch.user_id == user_id).delete()
            
            # Then delete from tables that are referenced by the above tables
            db.query(APIKey).filter(APIKey.user_id == user_id).delete()
            db.query(Coupon).filter(Coupon.redeemed_by == user_id).delete()
            db.query(Limits).filter(Limits.user_id == user_id).delete()
            
            # Delete wallet which has a one-to-one relationship with user
            db.query(Wallet).filter(Wallet.user_id == user_id).delete()
            
            # Finally delete the user record
            db.query(User).filter(User.id == user_id).delete()
            
            db.commit()
            logger.info(f"Successfully deleted all data for user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting all data for user: {e}")
            db.rollback()
            return False

def toggle_auto_topup(user_id: UUID, enabled: bool, amount: Optional[float] = None) -> User:
    """Toggle auto-topup setting for a user and optionally update the amount"""
    try:
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found for ID: {user_id}")
                raise ValueError("User not found")

            user.auto_topup = enabled

            # Update auto-topup amount if provided
            if amount is not None:
                if amount < 10.0:
                    logger.error(f"Provided amount is below minimum: {amount}")
                    raise ValueError("Minimum auto-topup amount is $10")
                user.auto_topup_amount = amount

            db.commit()
            db.refresh(user)
            logger.info(f"Auto-topup updated for user ID: {user_id}, enabled: {enabled}, amount: {amount}")
            return user
    except Exception as e:
        logger.error(f"Error toggling auto-topup for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error toggling auto-topup - {str(e)}")

## Wallet

def create_get_user_wallet(user_id: UUID) -> Wallet:
    """Get a user's wallet or create one if it doesn't exist"""
    try:
        with get_db_context() as db:
            wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
            if not wallet:
                wallet = Wallet(user_id=user_id, balance=0.0)
                db.add(wallet)
                db.commit()
                db.refresh(wallet)
                logger.info(f"Wallet created for user ID: {user_id}")
            else:
                logger.info(f"Wallet already exists for user ID: {user_id}")
            return wallet
    except Exception as e:
        logger.error(f"Error getting or creating user wallet for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting or creating user wallet")

def update_wallet_balance(email: str, amount: float) -> Dict[str, Any]:
    """Update wallet balance for a user by email"""
    try:
        with get_db_context() as db:
            # Find user by email
            user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.error(f"User not found for email: {email}")
                raise HTTPException(status_code=404, detail="User not found")

            # Get or create wallet
            wallet = db.query(Wallet).filter(Wallet.user_id == user.id).first()
            if not wallet:
                wallet = Wallet(user_id=user.id, balance=amount)
                db.add(wallet)
            else:
                wallet.balance = amount

            db.commit()
            db.refresh(wallet)
            logger.info(f"Wallet balance updated for user email: {email}, new balance: {amount}")
            
            return {
                "email": email,
                "balance": wallet.balance
            }
            
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error updating wallet balance for email: {email}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error updating wallet balance")

def get_all_wallets() -> List[Dict[str, Any]]:
    """Get all wallets with associated user emails"""
    try:
        with get_db_context() as db:
            wallets = db.query(Wallet, User.email).join(
                User, User.id == Wallet.user_id
            ).all()
            return [
                {
                    "email": email,
                    "balance": wallet.balance
                }
                for wallet, email in wallets
            ]
    except Exception as e:
        logger.error(f"Error getting all wallets: {e}")
        raise HTTPException(status_code=500, detail="Error getting all wallets")

def can_perform_evaluation(user_id: UUID) -> bool:
    """Check if user has enough balance for an evaluation"""
    try:
        wallet = create_get_user_wallet(user_id)
        if wallet.balance < evaluation_cost:
            logger.error(f"User with ID {user_id} does not have enough balance for an evaluation.")
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking balance for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error checking balance")

## Transaction

def get_transactions(user_id: UUID):
    try:
        with get_db_context() as db:
            transactions = db.query(Transaction).filter(
                Transaction.user_id == user_id
            ).order_by(Transaction.updated_at.desc()).all()
            
            return {
                "transactions": [
                    {
                        "id": tx.id,
                        "amount": tx.amount,
                        "type": tx.transaction_type,
                        "status": tx.status,
                        "date": tx.updated_at.isoformat()
                    }
                    for tx in transactions
                ]
            }
    except Exception as e:
        logger.error(f"Error getting transactions for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error getting transactions")

## Stripe

def create_get_stripe_customer(user_id: UUID) -> str:
    """Create a Stripe customer for a user"""
    try:
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"User not found for ID: {user_id}")
                raise ValueError("User not found")
            
            if user.stripe_customer_id:
                return user.stripe_customer_id
            
            customer_id = stripe_service.create_customer(user.email, user.email)
            user.stripe_customer_id = customer_id
            db.commit()
            
            return customer_id
    except Exception as e:
        logger.error(f"Error creating Stripe customer for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error creating Stripe customer")

def create_subscription_checkout(user_id: UUID, success_url: str, cancel_url: str) -> Dict[str, Any]:
    """Create a checkout session for initial subscription payment"""
    with get_db_context() as db:
        # Ensure user has a Stripe customer ID
        try:
            customer_id = create_get_stripe_customer(user_id)
        except ValueError as e:
            logger.error(f"Error creating Stripe customer for user ID: {user_id}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error creating Stripe customer")
        
        # Create transaction record
        try:
            transaction = Transaction(
                user_id=user_id,
                amount=subscription_amount,
                status="pending",
                transaction_type="subscription"  # This is just for labeling, not actual Stripe subscription
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
        except Exception as e:
            logger.error(f"Error creating transaction for user ID: {user_id}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error creating transaction")
        
        # Append transaction ID to success URL for tracking
        success_url = f"{success_url}?transaction_id={transaction.id}"
        
        # Create checkout session
        try:
            session = stripe_service.create_checkout_session(
                customer_id=customer_id,
                amount=subscription_amount,
                success_url=success_url,
                cancel_url=cancel_url,
                payment_type="subscription"  # This is just for labeling, not actual Stripe subscription
            )
        except Exception as e:
            logger.error(f"Error creating checkout session for user ID: {user_id}, error: {str(e)}")
            raise HTTPException(status_code=500, detail="Error creating checkout session")
        
        return {
            "transaction_id": transaction.id,
            "session_id": session.id,
            "checkout_url": session.url
        }

def create_topup_checkout(user_id: UUID, amount: float, success_url: str, cancel_url: str) -> Dict[str, Any]:
    """Create a checkout session for manual wallet top-up"""
    try:
        with get_db_context() as db:
            # Ensure user has a Stripe customer ID
            try:
                customer_id = create_get_stripe_customer(user_id)
            except Exception as e:
                logger.error(f"Error creating Stripe customer for user ID: {user_id}, error: {str(e)}")
                raise HTTPException(status_code=500, detail="Error creating Stripe customer")

            # Create transaction record
            try:
                transaction = Transaction(
                    user_id=user_id,
                    amount=amount,
                    status="pending",
                    transaction_type="topup"
                )
                db.add(transaction)
                db.commit()
                db.refresh(transaction)
            except Exception as e:
                logger.error(f"Error creating transaction for user ID: {user_id}, error: {str(e)}")
                raise HTTPException(status_code=500, detail="Error creating transaction")

            # Append transaction ID to success URL for tracking
            success_url = f"{success_url}?transaction_id={transaction.id}"

            # Create checkout session
            try:
                session = stripe_service.create_checkout_session(
                    customer_id=customer_id,
                    amount=amount,
                    success_url=success_url,
                    cancel_url=cancel_url,
                    payment_type="topup",
                    metadata={
                        "transaction_id": str(transaction.id),
                        "user_id": str(user_id),
                        "type": "topup"
                    }
                )
            except Exception as e:
                logger.error(f"Error creating checkout session for user ID: {user_id}, error: {str(e)}")
                raise HTTPException(status_code=500, detail="Error creating checkout session")

            return {
                "transaction_id": transaction.id,
                "session_id": session.id,
                "checkout_url": session.url
            }
    except Exception as e:
        logger.error(f"Error during top-up checkout creation for user ID: {user_id}, error: {str(e)}")
        raise HTTPException(status_code=500, detail="Error during checkout creation")

def handle_payment_success(payment_intent_data: Dict[str, Any]) -> None:
    """Handle successful payment from Stripe webhook"""
    try:
        with get_db_context() as db:
            amount = payment_intent_data.get("amount") / 100.0  # Convert from cents to dollars
            payment_intent_id = payment_intent_data.get("id")
            metadata = payment_intent_data.get("metadata", {})
            transaction_id = metadata.get("transaction_id")
            user_id = metadata.get("user_id")

            # Find pending transaction
            if not transaction_id:
                logger.error(f"No transaction_id in metadata for payment_intent_id={payment_intent_id}")
                return
            
            # Check if this payment has already been processed
            processed_payment = db.query(Transaction).filter(
                Transaction.id == transaction_id,
                Transaction.status == "succeeded"
            ).first()
            if processed_payment:
                logger.info(f"Payment {payment_intent_id} already processed, skipping")
                return processed_payment
                
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id
            ).first()
            
            if not transaction:
                logger.error(f"Transaction not found with ID {transaction_id} for user {user_id}")
                return
                
            logger.info(f"Found transaction: id={transaction.id}, status={transaction.status}, type={transaction.transaction_type}")
            
            # Update transaction status
            transaction.status = "succeeded"
            transaction.stripe_payment_intent_id = payment_intent_id
            
            # Update wallet balance
            wallet = create_get_user_wallet(user_id)
            wallet = db.merge(wallet)
            previous_balance = wallet.balance
            wallet.balance += amount
            
            logger.info(f"Updating wallet for user {user_id}: previous_balance=${previous_balance}, new_balance=${wallet.balance}")
            
            # Explicitly commit the transaction update
            db.commit()
            db.refresh(transaction)
            db.refresh(wallet)
            
            logger.info(f"Payment for user {user_id} with transaction ID {transaction.id} succeeded. Updated transaction status to succeeded")
            return transaction
    except Exception as e:
        logger.error(f"Error handling payment success: transaction_id={transaction_id}, error: {str(e)}")
        # Log the full traceback for better debugging
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")

def handle_payment_failed(payment_intent_data: Dict[str, Any]) -> None:
    """Handle failed payment from Stripe webhook"""
    try:
        with get_db_context() as db:
            metadata = payment_intent_data.get("metadata", {})
            transaction_id = metadata.get("transaction_id")
            
            # Find pending transaction
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
            ).first()
            
            if not transaction:
                logger.error(f"Pending transaction not found - {transaction_id}")   
                return
            
            # Update transaction status
            transaction.status = "failed"
            db.commit()
    except Exception as e:
        logger.error(f"Error handling payment failed for transaction {transaction_id}, error: {str(e)}")

def handle_payment_canceled(payment_intent_data: Dict[str, Any]) -> None:
    """Handle canceled payment from Stripe webhook"""
    try:
        with get_db_context() as db:
            metadata = payment_intent_data.get("metadata", {})
            transaction_id = metadata.get("transaction_id")
            
            # Find pending transaction
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
            ).first()
            
            if transaction:
                # Update transaction status
                transaction.status = "canceled"
                db.commit()
    except Exception as e:
        logger.error(f"Error handling payment canceled for transaction {transaction_id}, error: {str(e)}")

def handle_payment_expired(payment_intent_data: Dict[str, Any]) -> None:
    """Handle expired payment from Stripe webhook"""
    try:
        with get_db_context() as db:
            metadata = payment_intent_data.get("metadata", {})
            transaction_id = metadata.get("transaction_id")
            
            # Find pending transaction
            transaction = db.query(Transaction).filter(
                Transaction.id == transaction_id,
            ).first()

            if transaction:
                # Update transaction status
                transaction.status = "canceled"
                db.commit()
    except Exception as e:
        logger.error(f"Error handling payment expired for transaction {transaction_id}, error: {str(e)}")

def has_made_initial_payment(user_id: UUID) -> bool:
    """Check if user has made the initial subscription payment"""
    try:
        with get_db_context() as db:
            transaction = db.query(Transaction).filter(
                Transaction.user_id == user_id,
                Transaction.transaction_type == "subscription",
                Transaction.status == "succeeded"
            ).first()
            
            return transaction is not None
    except Exception as e:
        logger.error(f"Error checking if user {user_id} has made initial payment, error: {str(e)}")
        return False

def check_if_auto_topup_enabled(user_id: UUID) -> bool:
    """Check if auto-topup is enabled for a user"""
    try:
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            return user.auto_topup
    except Exception as e:
        logger.error(f"Error checking if auto-topup is enabled for user {user_id}, error: {str(e)}")
        return False

def auto_topup(user_id: UUID) -> Tuple[bool, Union[Transaction, str]]:
    try:
        with get_db_context() as db:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                raise ValueError("User not found")
            
            if not user.auto_topup:
                logger.info(f"Auto-topup is not enabled for user {user_id}")
                return False, "Auto-topup is not enabled"
            
            default_payment_method = stripe_service.retrieve_default_payment_method(user.stripe_customer_id)
            if not default_payment_method:
                logger.error(f"No default payment method found for user {user_id}")
            
                # Get the customer's payment methods
                payment_methods = stripe_service.get_payment_methods(user.stripe_customer_id)

                # Use the first available payment method
                if not payment_methods:
                    logger.error(f"No payment methods found for user {user_id}")
                    return False, "No payment methods found"
                payment_method_id = payment_methods[0].id
            else:
                payment_method_id = default_payment_method
            
            wallet = create_get_user_wallet(user_id)
            wallet = db.merge(wallet)
            
            # Create auto-topup transaction
            topup_transaction = Transaction(
                user_id=user_id,
                amount=user.auto_topup_amount,
                status="pending",
                transaction_type="auto_topup"
            )
            db.add(topup_transaction)
            db.flush()
            
            # Create payment intent for auto-topup
            try:
                payment_intent = stripe_service.create_payment_intent(
                    amount=user.auto_topup_amount,
                    customer_id=user.stripe_customer_id,
                    metadata={
                        "transaction_id": topup_transaction.id,
                        "user_id": user.id,
                        "type": "auto_topup"
                    },
                    payment_method_id=payment_method_id
                )
                
                # Update transaction with payment intent ID
                topup_transaction.stripe_payment_intent_id = payment_intent.id
                
                # Update transaction status
                topup_transaction.status = "succeeded"
                
                # Update wallet balance
                wallet.balance += subscription_amount
                
                db.commit()
                logger.info(f"Auto-topup succeeded for user {user_id}")
                return True, topup_transaction
            except Exception as e:
                logger.error(f"Auto-topup failed: {str(e)}")
                return False, f"Auto-topup failed - {str(e)}"
    except Exception as e:
        logger.error(f"Error processing auto-topup for user {user_id}, error: {str(e)}")
        return False, f"Error processing auto-topup - {str(e)}"

def charge_for_evaluation(user_id: UUID) -> Optional[Transaction]:
    """Charge user for an evaluation and update the wallet balance"""
    with get_db_context() as db:
        wallet = create_get_user_wallet(user_id)
        wallet = db.merge(wallet)
        # Check if user has enough balance
        if wallet.balance < evaluation_cost:
            logger.error(f"User with ID {user_id} does not have enough balance for an evaluation.")
            raise HTTPException(status_code=400, detail="User does not have enough balance for an evaluation.")
        
        # Create transaction for the evaluation
        transaction = Transaction(
            user_id=user_id,
            amount=evaluation_cost,
            status="succeeded",
            transaction_type="evaluation"
        )
        db.add(transaction)
        db.flush()
        
        # Update wallet balance
        wallet.balance -= evaluation_cost
        db.commit()

        # Make a copy of transaction attributes before session closes
        transaction = {
            "id": transaction.id,
            "user_id": transaction.user_id,
            "amount": transaction.amount,
            "status": transaction.status,
            "transaction_type": transaction.transaction_type
        }
        return transaction


## API Keys

def create_api_key(
    user_id: uuid.UUID,
    name: str,
) -> tuple[APIKey, str]:
    """
    Create a new API key with a specific name.
    Returns both the API key object and the raw key (which won't be stored directly in DB).
    """
    with get_db_context() as db:
        try:
            # Check if API key with same name already exists
            existing_key = db.query(APIKey).filter(
                APIKey.name == name,
                APIKey.user_id == user_id
            ).first()
            if existing_key:
                logger.error(f"API key with name '{name}' already exists")
                raise HTTPException(
                    status_code=400, 
                    detail="API key with this name already exists."
                )

            # Generate new API key
            api_key = generate_api_key()
            key_hash = hash_api_key(api_key)

            db_api_key = APIKey(
                user_id=user_id,
                key_hash=key_hash,
                name=name,
            )

            db.add(db_api_key)
            db.commit()
            db.refresh(db_api_key)
            logger.info(f"Created API key '{name}'")
            return db_api_key, api_key

        except IntegrityError as e:
            db.rollback()
            logger.error(f"Integrity error while creating API key: {str(e)}")
            raise HTTPException(
                status_code=400, 
                detail="API key with this name already exists for this project"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Error while creating API key: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

def delete_api_key(key_id: uuid.UUID) -> bool:
    """Delete an API key"""
    with get_db_context() as db:
        try:
            db_api_key = db.query(APIKey).filter(
                APIKey.id == key_id,
            ).first()

            if not db_api_key:
                logger.error(f"API key not found ")
                raise HTTPException(status_code=404, detail="API key not found")

            db.delete(db_api_key)
            db.commit()
            logger.info(f"Deleted API key")
            return True
        except IntegrityError as e:
            logger.error(f"Integrity error while deleting API key: {str(e)}")
            raise HTTPException(status_code=400, detail="API key is in use")
        except Exception as e:
            logger.error(f"Error while deleting API key: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

def list_api_keys(user_id: uuid.UUID) -> List[APIKey]:
    """Get all API keys for a specific user."""
    with get_db_context() as db:
        try:
            api_keys = db.query(APIKey).filter(
                APIKey.user_id == user_id,
            ).all()
            logger.info(f"Found {len(api_keys)} API keys for user")
            return api_keys
        except Exception as e:
            logger.error(f"Error while fetching API keys for user: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

def update_api_key_name(
    key_id: uuid.UUID,
    user_id: uuid.UUID,
    new_name: str
) -> APIKey:
    """Update the name of an API key."""
    with get_db_context() as db:
        try:
            db_api_key = db.query(APIKey).filter(
                APIKey.id == key_id,
            ).first()

            if not db_api_key:
                raise HTTPException(status_code=404, detail="API key not found")

            # Check if new name already exists for this user
            existing_key = db.query(APIKey).filter(
                APIKey.name == new_name,
                APIKey.id != key_id,
                APIKey.user_id == user_id
            ).first()
            if existing_key:
                raise HTTPException(
                    status_code=400, 
                    detail="API key with this name already exists for the user"
                )

            db_api_key.name = new_name
            db.commit()
            db.refresh(db_api_key)
            logger.info(f"Updated API key name to '{new_name}' for key {key_id}")
            return db_api_key

        except HTTPException as e:
            raise e
        except Exception as e:
            db.rollback()
            logger.error(f"Error while updating API key name {key_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")

def get_api_key_details_from_hash(key_hash: str) -> Optional[APIKey]:
    """
    Retrieve API key details using the key hash.
    Returns the API key object with associated details.
    """
    with get_db_context() as db:
        try:
            api_key = db.query(APIKey).filter(
                APIKey.key_hash == key_hash
            ).first()

            if api_key is None:
                logger.error(f"No API key found for provided hash")
                return None
            logger.info(f"Found API key details for hash {key_hash}")
            return api_key

        except HTTPException as e:
            raise e
        except Exception as e:
            logger.error(f"Error while fetching API key details from hash: {str(e)}")
            raise HTTPException(status_code=500, detail="Internal Server Error")


## Coupon

def create_coupon(amount: float, email: str) -> Optional[Dict[str, Any]]:
    """Create a new coupon code and send it via email"""
    with get_db_context() as db:
        # Generate a unique coupon code
        while True:
            code = generate_coupon_code()
            existing = db.query(Coupon).filter(Coupon.code == code).first()
            if not existing:
                break
        
        # Create coupon record
        coupon = Coupon(
            code=code,
            amount=amount,
            is_redeemed=False,
        )
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
        
        # Send email with coupon code
        email_sent = send_coupon(
            email=email,
            coupon_code=code,
            amount=amount
        )
        
        if not email_sent:
            logger.error(f"Failed to send coupon email to {email}")
        
        return {
            "code": code,
            "amount": amount,
            "email_sent": email_sent
        }

def redeem_coupon(user_id: int, coupon_code: str) -> Optional[Dict[str, Any]]:
    """Redeem a coupon code for a user"""
    with get_db_context() as db:
        # Find the coupon
        coupon = db.query(Coupon).filter(Coupon.code == coupon_code).first()
        
        if not coupon:
            return None
        
        # Check if already redeemed
        if coupon.is_redeemed:
            return {"error": "Coupon has already been redeemed"}
        
        # Get user's wallet
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"error": "User not found"}
        
        wallet = db.query(Wallet).filter(Wallet.user_id == user_id).first()
        if not wallet:
            wallet = Wallet(user_id=user_id, balance=0.0)
            db.add(wallet)
        
        # Update wallet balance
        wallet.balance += coupon.amount
        
        # Add transaction
        transaction = Transaction(
            user_id=user_id,
            amount=coupon.amount,
            status="succeeded",
            transaction_type="coupon"
        )
        db.add(transaction)
        
        # Mark coupon as redeemed
        coupon.is_redeemed = True
        coupon.redeemed_by = user_id
        
        db.commit()
        
        return {
            "success": True,
            "amount": coupon.amount,
            "new_balance": wallet.balance
        }

## Deep Research

def create_deep_research(username: str, research: dict, user_id: uuid.UUID, run_id: UUID = None) -> Optional[DeepResearch]:
    """
    Create a new deep research record
    
    Args:
        username: Twitter username
        research: Research data dictionary
        user_id: UUID of the user
        run_id: UUID of the associated run
    
    Returns:
        Optional[DeepResearch]: Created deep research entry or None if error
    """
    with get_db_context() as db:
        try:
            logger.info(f"Creating deep research for username: {username}")
            deep_research = DeepResearch(
                username=username, 
                research=research, 
                user_id=user_id,
                run_id=run_id
            )
            db.add(deep_research)   
            db.commit()
            db.refresh(deep_research)
            logger.info(f"Successfully created deep research for username: {username}")
            return deep_research
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating deep research for username {username}: {e}")
            return None

def get_deep_research(username: str, user_id: uuid.UUID) -> Optional[DeepResearch]:
    """Get deep research record for a username"""
    with get_db_context() as db:
        try:
            logger.info(f"Fetching deep research for username: {username}")
            result = db.query(DeepResearch).filter(DeepResearch.username == username, DeepResearch.user_id == user_id).first()
            if result:
                logger.info(f"Found deep research for username: {username} and user_id: {user_id}")
            else:
                logger.info(f"No deep research found for username: {username} and user_id: {user_id}")
            return result
        except Exception as e:
            logger.error(f"Error fetching deep research for username {username} and user_id {user_id}: {e}")
            return None
    
def update_deep_research(username: str, research: dict, user_id: uuid.UUID, run_id: UUID = None) -> Optional[DeepResearch]:
    """
    Update deep research record for a username
    
    Args:
        username: Twitter username
        research: Research data dictionary
        user_id: UUID of the user
        run_id: UUID of the associated run (optional)
    
    Returns:
        Optional[DeepResearch]: Updated deep research entry or None if error
    """
    with get_db_context() as db:
        try:
            logger.info(f"Updating deep research for username: {username}")
            deep_research = db.query(DeepResearch).filter(DeepResearch.username == username, DeepResearch.user_id == user_id).first()
            if not deep_research:
                logger.warning(f"Cannot update deep research: no record found for username {username} and user_id {user_id}")
                return None
            deep_research.research = research
            if run_id:
                deep_research.run_id = run_id
            db.commit()
            db.refresh(deep_research)
            logger.info(f"Successfully updated deep research for username: {username} and user_id: {user_id}")
            return deep_research
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating deep research for username {username} and user_id {user_id}: {e}")
            return None

def delete_deep_research(username: str, user_id: uuid.UUID) -> bool:
    """Delete deep research record for a username"""
    with get_db_context() as db:
        try:
            logger.info(f"Deleting deep research for username: {username}")
            deep_research = db.query(DeepResearch).filter(DeepResearch.username == username, DeepResearch.user_id == user_id).first()
            if not deep_research:
                logger.warning(f"Cannot delete deep research: no record found for username {username} and user_id {user_id}")
                return False
            db.delete(deep_research)
            db.commit()
            logger.info(f"Successfully deleted deep research for username: {username} and user_id: {user_id}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting deep research for username {username} and user_id {user_id}: {e}")
            return False

def delete_user_data(username: str) -> dict:
    """
    Delete all data associated with a username from all tables except Run table.
    Run table entries are kept for billing and auditing purposes.
    
    Args:
        username: The username to delete data for
        
    Returns:
        Dictionary with deletion status for each table
    """
    results = {
        "twitter_user": False,
        "deep_research": False,
        "analysis_results": False,
        "tweets": False,
        "ip_conflict_analysis": False
    }
    
    with get_db_context() as db:
        try:
            logger.info(f"Deleting all data for username: {username}")
            
            # Delete from DeepResearch
            deep_research = db.query(DeepResearch).filter(DeepResearch.username == username).first()
            if deep_research:
                db.delete(deep_research)
                results["deep_research"] = True
                logger.info(f"Deleted deep research for username: {username}")
            
            # Delete from AnalysisResult
            analysis_results = db.query(ScamAnalysisResult).filter(ScamAnalysisResult.username == username).all()
            if analysis_results:
                for result in analysis_results:
                    db.delete(result)
                results["analysis_results"] = True
                logger.info(f"Deleted {len(analysis_results)} analysis results for username: {username}")
            
            # Delete from Tweet
            tweets = db.query(DBTweet).filter(DBTweet.username == username).all()
            if tweets:
                db.query(DBTweet).filter(DBTweet.username == username).delete(synchronize_session=False)
                results["tweets"] = True
                logger.info(f"Deleted {len(tweets)} tweets for username: {username}")
            
            # Delete from IPConflictAnalysis
            ip_conflict_analyses = db.query(IpConflictAnalysis).filter(IpConflictAnalysis.username == username).all()
            if ip_conflict_analyses:
                for analysis in ip_conflict_analyses:
                    db.delete(analysis)
                results["ip_conflict_analysis"] = True
                logger.info(f"Deleted {len(ip_conflict_analyses)} IP conflict analyses for username: {username}")
            
            # Delete from TwitterUser
            twitter_user = db.query(DBTwitterUser).filter(DBTwitterUser.username == username).first()
            if twitter_user:
                db.delete(twitter_user)
                results["twitter_user"] = True
                logger.info(f"Deleted twitter user for username: {username}")
                
            db.commit()
            logger.info(f"Successfully deleted all data for username: {username}")
            return results
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting data for username {username}: {e}")
            return results

def delete_all_tweets(username: str) -> bool:
    """Delete all tweets for a username"""
    with get_db_context() as db:
        try:
            logger.info(f"Deleting all tweets for username: {username}")
            db.query(DBTweet).filter(DBTweet.username == username).delete(synchronize_session=False)
            db.commit()
            logger.info(f"Successfully deleted all tweets for username: {username}")
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting tweets for username {username}: {e}")
            return False
## Token Risk Assessment

def create_token_risk_assessment(
    username: str,
    user_id: uuid.UUID,
    run_id: uuid.UUID,
    analysis_result_id: uuid.UUID,
    token_address: str,
    token_symbol: Optional[str],
    chain_id: Optional[str],
    risk_report: dict,
    risk_level: str,
    risk_score: float,
    confidence_score: Optional[float] = None,
    status: str = "Succeeded",
    fail_reason: Optional[str] = None,
) -> Optional[TokenRiskAssessment]:
    """
    Create a token risk assessment record.
    """
    with get_db_context() as db:
        try:
            tra = TokenRiskAssessment(
                username=username,
                user_id=user_id,
                run_id=run_id,
                analysis_result_id=analysis_result_id,
                token_address=token_address,
                token_symbol=token_symbol,
                chain_id=chain_id,
                risk_report=risk_report,
                risk_level=risk_level,
                risk_score=risk_score,
                confidence_score=confidence_score,
                status=status,
                fail_reason=fail_reason,
            )
            db.add(tra)
            db.commit()
            db.refresh(tra)
            return tra
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating token risk assessment for {username}: {e}")
            return None


def update_token_risk_assessment_status(
    tra_id: uuid.UUID,
    status: str,
    fail_reason: Optional[str] = None,
) -> Optional[TokenRiskAssessment]:
    """
    Update status / fail reason for a token risk assessment.
    """
    with get_db_context() as db:
        try:
            tra = db.query(TokenRiskAssessment).filter(TokenRiskAssessment.id == tra_id).first()
            if not tra:
                logger.warning(f"TokenRiskAssessment not found: {tra_id}")
                return None
            tra.status = status
            tra.fail_reason = fail_reason
            db.commit()
            db.refresh(tra)
            return tra
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating token risk assessment {tra_id}: {e}")
            return None


def get_token_risk_assessments(username: str, user_id: uuid.UUID) -> List[Dict[str, Any]]:
    """
    Fetch token risk assessments for a username and user.
    """
    with get_db_context() as db:
        try:
            rows = (
                db.query(TokenRiskAssessment)
                .filter(TokenRiskAssessment.username == username, TokenRiskAssessment.user_id == user_id)
                .order_by(TokenRiskAssessment.analyzed_at.desc())
                .all()
            )
            results = []
            for r in rows:
                results.append(
                    {
                        "id": str(r.id),
                        "username": r.username,
                        "token_address": r.token_address,
                        "token_symbol": r.token_symbol,
                        "chain_id": r.chain_id,
                        "risk_level": r.risk_level,
                        "risk_score": r.risk_score,
                        "confidence_score": r.confidence_score,
                        "status": r.status,
                        "fail_reason": r.fail_reason,
                        "risk_report": r.risk_report,
                        "run_id": str(r.run_id) if r.run_id else None,
                        "analysis_result_id": str(r.analysis_result_id) if r.analysis_result_id else None,
                        "analyzed_at": r.analyzed_at.isoformat() if r.analyzed_at else None,
                    }
                )
            return results
        except Exception as e:
            logger.error(f"Error fetching token risk assessments for {username}: {e}")
            return []
