from datetime import datetime
from typing import List, Dict
from math import ceil

def create_content_chunks_prev(tweets: List[Dict], retweets: List[Dict], max_chunk_size: int = 12) -> List[Dict]:
    """
    Creates balanced chunks of tweets and retweets based on content size.
    
    Args:
        tweets: List of tweet dictionaries
        retweets: List of retweet dictionaries
        max_chunk_size: Maximum size of each chunk (tweets + retweets)
        
    Returns:
        List of chunks, each containing balanced tweets and retweets lists
    """
    # Calculate ratio to maintain proportion
    total_content = len(tweets) + len(retweets)
    num_chunks = ceil(total_content / max_chunk_size)
    
    # Calculate items per chunk while maintaining ratio
    tweets_ratio = len(tweets) / total_content
    retweets_ratio = len(retweets) / total_content
    
    tweets_per_chunk = ceil(tweets_ratio * max_chunk_size)
    retweets_per_chunk = max_chunk_size - tweets_per_chunk
    
    chunks = []
    for i in range(num_chunks):
        tweet_start = i * tweets_per_chunk
        tweet_end = min((i + 1) * tweets_per_chunk, len(tweets))
        
        retweet_start = i * retweets_per_chunk
        retweet_end = min((i + 1) * retweets_per_chunk, len(retweets))
        
        # Only add chunk if there's content
        if tweet_start < len(tweets) or retweet_start < len(retweets):
            chunk = {
                "tweets": tweets[tweet_start:tweet_end],
                "retweets": retweets[retweet_start:retweet_end]
            }
            chunks.append(chunk)
    
    return chunks

def create_content_chunks(tweets: List[Dict], retweets: List[Dict], max_chunk_size: int = 30) -> List[Dict]:
    """
    Creates balanced chunks of tweets and retweets based on content size.
    Preserves all tweet data including URLs and mentioned usernames.
    
    Args:
        tweets: List of tweet dictionaries
        retweets: List of retweet dictionaries
        max_chunk_size: Maximum size of each chunk (tweets + retweets)
        
    Returns:
        List of chunks, each containing balanced tweets and retweets lists
    """
    # Calculate ratio to maintain proportion
    total_content = len(tweets) + len(retweets)
    num_chunks = ceil(total_content / max_chunk_size)
    
    # Calculate items per chunk while maintaining ratio
    tweets_ratio = len(tweets) / total_content if total_content > 0 else 0
    retweets_ratio = len(retweets) / total_content if total_content > 0 else 0
    
    tweets_per_chunk = ceil(tweets_ratio * max_chunk_size)
    retweets_per_chunk = max_chunk_size - tweets_per_chunk
    
    chunks = []
    for i in range(num_chunks):
        tweet_start = i * tweets_per_chunk
        tweet_end = min((i + 1) * tweets_per_chunk, len(tweets))
        
        retweet_start = i * retweets_per_chunk
        retweet_end = min((i + 1) * retweets_per_chunk, len(retweets))
        
        # Only add chunk if there's content
        if tweet_start < len(tweets) or retweet_start < len(retweets):
            chunk = {
                "tweets": tweets[tweet_start:tweet_end],
                "retweets": retweets[retweet_start:retweet_end]
            }
            chunks.append(chunk)
    
    return chunks

def format_from_date(date):
    return datetime.fromisoformat(date.replace('Z', '+00:00')).strftime('%Y-%m-%d')

def filter_tweets(all_tweets):
    tweets, retweets = [], []
    for i in all_tweets:
        if i['is_retweet']:
            retweets.append(i)
        else:
            tweets.append(i)
    return tweets, retweets