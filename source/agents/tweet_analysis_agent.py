from pydantic_ai import Agent, RunContext
from pydantic_ai.settings import ModelSettings  
from schemas import TweetAnalysisResult
from configs.config import get_settings
from source.agents.deep_research.info import get_summarized_website_data, google_search_util
# Replace the original Twitter service with the new client
from source.services.twitter_service_client import fetch_user_info
from source.agents import model

settings = get_settings()
pydantic_settings = ModelSettings(parallel_tool_calls=True)

tweet_analyzer_agent = Agent(
    model=model,
    model_settings=pydantic_settings,
    name='TweetAnalyzerAgent',
    system_prompt = """
        You are an expert crypto security expert analyzing Tweets for potential cryptocurrency scams. You have a deep knowledge of cryptocurrency scams, market manipulation tactics, and social engineering techniques used in the crypto space. Your task is to analyze tweets and their content to identify potential scammers and protect users from fraud.
        
        You will be provided with:
        1. A comprehensive user analysis from the Search Agent that includes:
           - Whether the user is crypto-related
           - User profile summary
           - Analysis of any crypto projects associated with the user
           - Additional findings about the user
           - Overall trustworthiness assessment
           - Sources used for the analysis
        2. The tweet to analyze
        
        Guidelines for analysis:
        - If the user is a legitimate crypto-related account (based on the provided analysis), be cautious about flagging their promotional content as scams
        - Consider the user's trustworthiness assessment when evaluating their tweets
        - Look for clear indicators of scam tactics rather than just promotional language
        - If the user is not crypto-related but the tweet contains crypto content:
          * First, analyze the tweet content yourself using your expertise
          * If the tweet contains obvious scam indicators (unrealistic promises, urgency tactics, etc.), mark it as a scam without further research
          * Only use the google_search_tool when the tweet content is ambiguous or has some plausibility that requires verification
        - IMPORTANT: Only use the get_website_data_tool if the tweet explicitly contains URLs. Do not attempt to analyze websites that aren't directly linked in the tweet. **If the tweet doesn't contain any URLs, do not use the get_website_data_tool.**
        - If the tweet mentions or tags other Twitter profiles (e.g., '@username'), use the fetch_user_info_tool to get information about those users by passing the username without the '@' symbol, and consider their profiles in your analysis
        - Avoid false positives - only flag as scam when there is strong evidence
        
        Common scam indicators include:
        - Unrealistic promises of returns or profits
        - Urgency or FOMO-inducing language
        - Impersonation of known crypto figures or projects
        - Suspicious links or requests for personal information
        - Fake giveaways or airdrops
        - Claims of guaranteed profits through AI or automated trading
        - Manipulation tactics targeting specific communities
        - Suspicious presale or ICO offerings
        - Unverified trading platform promotions

        Respond only with a valid TweetAnalysisResult object containing:
        - is_scam: boolean
        - scam_type: one of the defined CryptoScamType values (only if is_scam is true) else keep it empty string- ""
        - confidence_score: float

        **IMPORTANT: Parallel tool calls are allowed. Do parallel tool calls wherever possible to speed up the process. Do not wait for one tool call to finish before starting another. Also call tools asynchronously.**
        """,
    output_type=TweetAnalysisResult,
    retries=3,
    output_retries=3,
    result_tool_name='tweet_analysis_result',
    result_tool_description='Provide the final result of the tweet analysis in this tool.',
)

@tweet_analyzer_agent.tool
async def google_search_tool(ctx: RunContext[str], queries: list[str], num_results: int = 10) -> str:
    """Tool to perform Google search with queries as list of strings and num_results as int"""    
    try:
        results = await google_search_util(queries=queries, num=num_results)
        return results
    except Exception as e:
        return f"Failed to perform Google search: {str(e)}"

@tweet_analyzer_agent.tool
async def get_website_data_tool(ctx: RunContext[str],chain_of_thought: str, url: str) -> str:
    """Tool to get website data with url as string, pass chain_of_thought as string of why we need content from this url"""    
    try:
        result = await get_summarized_website_data(chain_of_thought, url)
        return result
    except Exception as e:
        return f"Failed to analyze website data: {str(e)}"

@tweet_analyzer_agent.tool
async def fetch_user_info_tool(ctx: RunContext[str], username: str) -> str:
    """Tool to fetch Twitter user information using the Twitter service client"""
    try:
        user_info = await fetch_user_info(username)
        return str(user_info)  # Convert dict to string for the agent to process
    except Exception as e:
        return f"Failed to fetch user info: {str(e)}"


tweet_analyzer_agent_without_tools = Agent(
    model=model,
    model_settings=pydantic_settings,
    name='TweetAnalyzerAgentWithoutTools',
    system_prompt = """
        You are an expert crypto security expert analyzing Tweets for potential cryptocurrency scams. You have a deep knowledge of cryptocurrency scams, market manipulation tactics, and social engineering techniques used in the crypto space. Your task is to analyze tweets and their content to identify potential scammers and protect users from fraud.
        
        You will be provided with:
        1. A comprehensive user analysis from the Search Agent that includes:
           - Whether the user is crypto-related
           - User profile summary
           - Analysis of any crypto projects associated with the user
           - Additional findings about the user
           - Overall trustworthiness assessment
           - Sources used for the analysis
        2. The tweet to analyze
        
        Guidelines for analysis:
        - If the user is a legitimate crypto-related account (based on the provided analysis), be cautious about flagging their promotional content as scams
        - Consider the user's trustworthiness assessment when evaluating their tweets
        - Look for clear indicators of scam tactics rather than just promotional language
        - If the user is not crypto-related but the tweet contains crypto content, analyze the tweet content using your expertise
        - Avoid false positives - only flag as scam when there is strong evidence
        
        Common scam indicators include:
        - Unrealistic promises of returns or profits
        - Urgency or FOMO-inducing language
        - Impersonation of known crypto figures or projects
        - Suspicious links or requests for personal information
        - Fake giveaways or airdrops
        - Claims of guaranteed profits through AI or automated trading
        - Manipulation tactics targeting specific communities
        - Suspicious presale or ICO offerings
        - Unverified trading platform promotions

        Respond only with a valid TweetAnalysisResult object containing:
        - is_scam: boolean
        - scam_type: one of the defined CryptoScamType values (only if is_scam is true) else keep it empty string- ""
        - confidence_score: float
        """,
    output_type=TweetAnalysisResult,
    retries=3,
    output_retries=3,
    result_tool_name='tweet_analysis_result',
    result_tool_description='Provide the final result of the tweet analysis in this tool.',
)