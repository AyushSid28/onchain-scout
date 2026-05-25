from typing import Dict, List, Optional, Union, Tuple
from enum import Enum
from pydantic import BaseModel, SecretStr, UUID4, BaseModel, Field
from datetime import datetime

class CreateApiKeyRequest(BaseModel):
    name: str

class UpdateApiKeyRequest(BaseModel):
    new_name: str
    key_id: UUID4

class APIKeyResponse(BaseModel):
    id: UUID4
    user_id: UUID4
    name: str
    api_key: str  # Only returned when key is first created
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
        'protected_namespaces': ()
    }

class APIKeyDB(BaseModel):
    id: UUID4
    user_id: UUID4
    name: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        'from_attributes': True,
        'protected_namespaces': ()
    }

class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str

class EvaluationType(str, Enum):
    """Type of evaluation to perform."""
    ADVANCED = "advanced"  # With Deep Research & Tweet Analyzer agent with tools
    BASIC = "basic"        # Without Deep Research & normal Tweet Analyzer agent without tools

class EvaluationRequest(BaseModel):
    x_profile : str
    project_name : Optional[str] = None
    project_description : Optional[str] = None
    evaluation_type : Optional[EvaluationType] = EvaluationType.ADVANCED  # Default to advanced evaluation
    token_name: Optional[str] = None  # Optional token name/symbol for risk assessment
    token_address : Optional[str] = None
    token_chain : Optional[str] = None
    token_risk : Optional[bool] = False

class CryptoAnalysis(BaseModel):
    name: str = Field(..., description="Name of the cryptocurrency project or coin")
    is_legitimate: bool = Field(..., description="Assessment of whether the project appears legitimate")
    team_background: str = Field(..., description="Information about the team behind the project")
    project_history: str = Field(..., description="Timeline and history of the project")
    security_concerns: List[str] = Field(default_factory=list, description="List of identified security concerns or red flags")
    audit_information: Optional[str] = Field(None, description="Information about security audits if available")
    community_feedback: str = Field(..., description="Summary of community sentiment and feedback")
    website_analysis: str = Field(..., description="Analysis of the project's website and online presence")
    overall_risk_assessment: str = Field(..., description="Overall risk assessment (Low, Medium, High)")

class DeepSearchResult(BaseModel):
    user_is_crypto_related: bool
    user_profile_summary: str
    cryptos: Optional[List[CryptoAnalysis]] = None
    additional_findings: Optional[str] = None
    trustworthiness_assessment: Optional[str] = None
    sources: List[str] = Field(default_factory=list)

class CryptoScamType(str, Enum):
    investment_scam = "investment_scam"
    impersonation_scam = "impersonation_scam"
    giveaway_scam = "giveaway_scam"
    verification_scam = "verification_scam"
    pig_butchering = "pig_butchering"
    fake_trading_platform = "fake_trading_platform"
    ai_trading_scam = "ai_trading_scam"
    affinity_scam = "affinity_scam"
    fake_ico = "fake_ico"
    fake_presale = "fake_presale"

class IncidentCreate(BaseModel):
    x_handle: str
    username: str
    project_website: str
    affiliated_handles: List[str]
    scam_type: CryptoScamType

class IncidentResponse(IncidentCreate):
    id: UUID4
    updated_at: datetime

class TweetAnalysisResult(BaseModel):
    is_scam: bool = Field(description="Whether the tweet is likely a scam tweet or not")
    scam_type: Union[CryptoScamType, str] = Field(default="", description="The type of scam the tweet is likely to be")
    confidence_score: float = Field(description="Confidence score of the analysis", ge=0, le=1)

class SeverityLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class ViolationType(str, Enum):
    IMPERSONATION = "impersonation"
    BRAND_MISUSE = "brand_misuse"
    FALSE_CLAIMS = "false_claims"

class Violation(BaseModel):
    content: str = Field(description="Content that violates IP")
    type: ViolationType = Field(description="Type of violation")
    description: str = Field(description="Description of violation")

class IPConflictAnalysis(BaseModel):
    has_violations: bool = Field(description="Whether violations were detected")
    violations: List[Violation] = Field(description="List of violations", default_factory=list)
    severity: SeverityLevel = Field(description="Overall severity level")
    recommendations: List[str] = Field(description="Recommended actions", default_factory=list)
    confidence: float = Field(description="Analysis confidence (0.0-1.0)", ge=0.0, le=1.0)

class ChunkAnalysisSummary(BaseModel):
    profile_summary: str

class AnalysisEvidence(BaseModel):
    info: str = Field(description="Detailed information about the finding")
    evidences: List[str] = Field(description="List of tweet examples supporting the finding, at max 3", default_factory=list)

class PromotionalActivity(AnalysisEvidence):
    pass

class EmotionalManipulation(AnalysisEvidence):
    pass

class SuspiciousPatterns(AnalysisEvidence):
    pass

class NetworkConnections(AnalysisEvidence):
    pass

class Analysis(BaseModel):
    promotional_activity: Optional[PromotionalActivity] = Field(description="Analysis of promotional activities", default=None)
    emotional_manipulation: Optional[EmotionalManipulation] = Field(description="Analysis of emotional manipulation tactics", default=None)
    suspicious_patterns: Optional[SuspiciousPatterns] = Field(description="Analysis of suspicious behavior patterns", default=None)
    network_connections: Optional[NetworkConnections] = Field(description="Analysis of network connections and interactions", default=None)
    content_themes: str = Field(description="Analysis of recurring content themes")
    technical_indicators: str = Field(description="Analysis of technical patterns")

class EnhancedChunkAnalysisSummary(BaseModel):
    profile_summary: str = Field(description="Comprehensive text summary of all findings")
    analysis: Analysis = Field(description="Detailed structured analysis of the profile")

class ScamAnalysisResult(BaseModel):
    profile_summary: str = Field(description="Comprehensive text summary of all findings")
    profile_analysis: Analysis = Field(description="Detailed profile analysis")
    is_scammer: bool = Field(description="Whether the account is likely a scammer")
    confidence_score: float = Field(description="Confidence score of the analysis", ge=0, le=1)
    scam_types: Optional[List[CryptoScamType]] = Field(description="Types of scams if detected")
    risk_level: SeverityLevel = Field(description="Overall risk level of the account")
    risk_factors: Optional[List[str]] = Field(description="List of identified risk factors")
    crypto_currencies: Optional[List[str]] = Field(description="Related cryptocurrencies mentioned")
    recommended_actions: List[str] = Field(description="Recommended actions based on findings")

# Technical Analysis Schemas
class TA_details(BaseModel):
    """Technical Analysis input data from technical indicators"""
    pair: str = Field(description="Trading pair (e.g., 'BTCUSD', 'ETHUSD')")
    interval: int = Field(description="Time interval in minutes")
    timestamp: str = Field(description="Analysis timestamp")
    current_price: Optional[float] = Field(None, description="Current price in USD")
    
    overall_signal: str = Field(description="Overall technical signal")
    signal_confidence: Dict = Field(description="Signal confidence breakdown")
    
    # Moving Averages
    moving_averages: Dict = Field(description="Moving averages data including SMA and EMA values")
    
    # RSI
    rsi: Dict = Field(description="RSI data including value and signal")
    
    # MACD
    macd: Dict = Field(description="MACD data including lines and histogram")
    
    # OBV
    obv: Dict = Field(description="OBV data including value and signal")
    
    # Support/Resistance
    support_resistance: Dict = Field(description="Support and resistance levels")
    
    # Trend Analysis
    trend: Dict = Field(description="Trend analysis including direction and strength")

class TA_report(BaseModel):
    """Comprehensive Technical Analysis Report generated by the agent"""
    pair: str = Field(description="Trading pair analyzed")
    interval: int = Field(description="Time interval used")
    timestamp: str = Field(description="Analysis timestamp")
    
    # Overall Analysis
    overall_signal: str = Field(description="Overall technical signal (bullish/bearish/neutral)")
    signal_strength: str = Field(description="Strength of the signal (strong/moderate/weak)")
    confidence_level: float = Field(description="Confidence level (0.0-1.0)")
    
    # Moving Averages Analysis
    moving_averages_analysis: str = Field(description="Detailed moving averages analysis")
    sma_analysis: str = Field(description="Simple Moving Average analysis")
    ema_analysis: str = Field(description="Exponential Moving Average analysis")
    ma_signal: str = Field(description="Moving averages signal")
    
    # RSI Analysis
    rsi_analysis: str = Field(description="Detailed RSI analysis")
    rsi_value: Optional[float] = Field(description="Current RSI value")
    rsi_signal: str = Field(description="RSI signal interpretation")
    overbought_oversold: str = Field(description="Overbought/oversold assessment")
    
    # MACD Analysis
    macd_analysis: str = Field(description="Detailed MACD analysis")
    macd_line: Optional[float] = Field(description="MACD line value")
    signal_line: Optional[float] = Field(description="Signal line value")
    histogram: Optional[float] = Field(description="MACD histogram value")
    macd_signal: str = Field(description="MACD signal interpretation")
    crossover_analysis: str = Field(description="MACD crossover analysis")
    
    # OBV Analysis
    obv_analysis: str = Field(description="Detailed OBV analysis")
    obv_value: Optional[float] = Field(description="Current OBV value")
    obv_signal: str = Field(description="OBV signal interpretation")
    volume_confirmation: str = Field(description="Volume confirmation analysis")
    
    # Support/Resistance Analysis
    support_resistance_analysis: str = Field(description="Detailed support/resistance analysis")
    nearest_support: Optional[float] = Field(description="Nearest support level")
    nearest_resistance: Optional[float] = Field(description="Nearest resistance level")
    price_position: str = Field(description="Current price position relative to levels")
    breakout_potential: str = Field(description="Breakout potential analysis")
    
    # Trend Analysis
    trend_analysis: str = Field(description="Detailed trend analysis")
    trend_direction: str = Field(description="Trend direction")
    trend_strength: str = Field(description="Trend strength")
    trend_continuation: str = Field(description="Trend continuation probability")
    
    # Pattern Recognition
    chart_patterns: List[str] = Field(default_factory=list, description="Identified chart patterns")
    pattern_significance: str = Field(description="Pattern significance analysis")
    
    # Risk Assessment
    risk_level: str = Field(description="Technical risk level")
    risk_factors: List[str] = Field(default_factory=list, description="Technical risk factors")
    stop_loss_recommendations: List[str] = Field(default_factory=list, description="Stop loss recommendations")
    
    # Trading Recommendations
    short_term_outlook: str = Field(description="Short-term price outlook")
    medium_term_outlook: str = Field(description="Medium-term price outlook")
    entry_points: List[str] = Field(default_factory=list, description="Recommended entry points")
    exit_strategies: List[str] = Field(default_factory=list, description="Recommended exit strategies")
    
    # Summary
    executive_summary: str = Field(description="Executive summary of technical analysis")
    key_insights: List[str] = Field(default_factory=list, description="Key technical insights")
    actionable_recommendations: List[str] = Field(default_factory=list, description="Actionable trading recommendations")

# Fundamental Analysis Schemas
class FA_details(BaseModel):
    """Fundamental Analysis input data fetched from CoinGecko API"""
    whitepaper_url: Optional[str] = Field(None, description="Whitepaper URL from links.whitepaper")
    team_background: str = Field(description="Development team background from links.repos_url.github, links.subreddit_url, developer_data")
    project_technology: str = Field(description="Project technology and innovation from description, categories")
    current_price: Optional[float] = Field(None, description="Current price in USD from market_data.current_price.usd")
    market_capitalization: Optional[float] = Field(None, description="Market capitalization from market_cap_rank or market_data.market_cap.usd")
    circulating_supply: Optional[float] = Field(None, description="Circulating supply from market_data.circulating_supply")
    total_supply: Optional[float] = Field(None, description="Total supply from market_data.total_supply")
    tokenomics_distribution: str = Field(description="Tokenomics distribution, inflation, reward mechanisms from market_data.max_supply, market_data.circulating_supply")
    adoption_rate: str = Field(description="Adoption rate from public_interest_stats, community_data, market_data")
    community_engagement: str = Field(description="Community engagement and activity from community_data")
    roadmap_strategy: str = Field(description="Roadmap and long-term strategy from description, links.homepage, links.announcement_url")

class FA_report(BaseModel):
    """Comprehensive Fundamental Analysis Report generated by the agent"""
    project_name: str = Field(description="Project name")
    project_description: str = Field(description="Detailed project description and analysis")
    categories: List[str] = Field(default_factory=list, description="Project categories")
    
    # Whitepaper Analysis
    whitepaper_analysis: str = Field(description="Analysis of whitepaper availability and quality")
    whitepaper_url: Optional[str] = Field(None, description="Whitepaper URL if available")
    
    # Team Analysis
    team_background_analysis: str = Field(description="Detailed team background and credibility analysis")
    team_strengths: List[str] = Field(default_factory=list, description="Team strengths")
    team_weaknesses: List[str] = Field(default_factory=list, description="Team weaknesses")
    
    # Technology Analysis
    technology_analysis: str = Field(description="Detailed technology and innovation analysis")
    technology_stack: str = Field(description="Technology stack assessment")
    innovation_level: str = Field(description="Innovation level assessment")
    
    # Market Analysis
    current_price: Optional[float] = Field(None, description="Current price in USD")
    market_capitalization: Optional[float] = Field(None, description="Market capitalization")
    market_cap_analysis: str = Field(description="Market cap analysis and implications")
    market_position: str = Field(description="Market position and competitive analysis")
    
    # Supply Analysis
    circulating_supply: Optional[float] = Field(None, description="Circulating supply")
    total_supply: Optional[float] = Field(None, description="Total supply")
    supply_analysis: str = Field(description="Supply distribution and inflation analysis")
    
    # Tokenomics Analysis
    tokenomics_analysis: str = Field(description="Comprehensive tokenomics analysis")
    token_utility: str = Field(description="Token utility assessment")
    economic_model: str = Field(description="Economic model analysis")
    
    # Adoption Analysis
    adoption_analysis: str = Field(description="Adoption rate and growth analysis")
    user_base: str = Field(description="User base assessment")
    growth_potential: str = Field(description="Growth potential analysis")
    
    # Community Analysis
    community_analysis: str = Field(description="Community engagement and health analysis")
    community_strengths: List[str] = Field(default_factory=list, description="Community strengths")
    community_weaknesses: List[str] = Field(default_factory=list, description="Community weaknesses")
    
    # Roadmap Analysis
    roadmap_analysis: str = Field(description="Roadmap and strategy analysis")
    development_timeline: str = Field(description="Development timeline assessment")
    strategic_vision: str = Field(description="Strategic vision analysis")
    
    # Risk Assessment
    risk_factors: List[str] = Field(default_factory=list, description="Identified risk factors")
    risk_level: str = Field(description="Overall risk level (Low/Medium/High)")
    risk_mitigation: str = Field(description="Risk mitigation strategies")
    
    # Strengths and Weaknesses
    project_strengths: List[str] = Field(default_factory=list, description="Project strengths")
    project_weaknesses: List[str] = Field(default_factory=list, description="Project weaknesses")
    
    # Investment Assessment
    investment_potential: str = Field(description="Investment potential assessment")
    long_term_outlook: str = Field(description="Long-term outlook")
    short_term_outlook: str = Field(description="Short-term outlook")
    
    # Summary
    executive_summary: str = Field(description="Executive summary")
    key_recommendations: List[str] = Field(default_factory=list, description="Key recommendations")


### Final Crypto Analysis Schema

class ForecastOutlook(BaseModel):
    """Structured forecast and future price movement prediction for a cryptocurrency"""
    future_movement_prediction: str = Field(description="Overall directional call (Bullish, Bearish, Sideways, Volatile)")
    prediction_timeframe: str = Field(description="Time horizon (e.g., Next 1 month, Q3 2025, 12 months)")
    prediction_rationale: str = Field(description="Why the forecast is made, based on TA, FA, deep research")
    key_prediction_assumptions: List[str] = Field(description="Assumptions that must hold true for the forecast")
    catalyst_events: List[str] = Field(description="Key upcoming events that may influence price")
    macro_factors_considered: List[str] = Field(description="Macroeconomic, regulatory, or geopolitical factors accounted for")
    leading_indicators_to_watch: List[str] = Field(description="Metrics or events that validate or negate the prediction")
    best_case_scenario: str = Field(description="Optimistic outlook with justification")
    base_case_scenario: str = Field(description="Most probable outcome with justification")
    worst_case_scenario: str = Field(description="Adverse condition and expected result")
    scenario_probabilities: Optional[Dict[str, float]] = Field(
        description="Assigned probabilities for bull/base/bear cases, e.g., {'bull': 0.2, 'base': 0.6, 'bear': 0.2}"
    )
    forecast_confidence_pct: Optional[float] = Field(description="Confidence in the forecast (0-100%)")
    forecasted_price_range: Optional[Dict[str, Tuple[float, float]]] = Field(
        default=None,
        description="Expected price ranges for each scenario (e.g., {'bull': (4000, 4500), 'base': (3000, 3400), 'bear': (2200, 2700)})"
    )


class Final_CryptoAnalysis_Report(BaseModel):
    """Comprehensive Final Crypto Analysis Report combining Fundamental, Technical, Deep Research, and Forecast insights"""

    # Basic Project Information
    crypto_name: str = Field(description="Cryptocurrency name")
    symbol: str = Field(description="Symbol (e.g., BTC, ETH)")
    project_category: str = Field(description="Primary category/sector of the project (e.g., DeFi, Layer 1)")

    # Executive Summary
    executive_summary: str = Field(description="Summarized analysis with highlights across all domains")
    final_rating: str = Field(description="Overall rating (e.g., Strong Buy, Buy, Hold, Sell, Avoid)")
    confidence_level_pct: Optional[float] = Field(description="Confidence level in the recommendation (0-100%)")
    recommended_action: str = Field(description="Recommended action (Buy/Sell/Hold)")
    investment_horizon: str = Field(description="Recommended time horizon (Short/Medium/Long Term)")

    # Fundamental Summary
    fundamental_strengths: List[str] = Field(description="Key fundamental strengths")
    fundamental_weaknesses: List[str] = Field(description="Key fundamental weaknesses")
    investment_potential: str = Field(description="Fundamental investment potential")
    risk_level_fundamental: str = Field(description="Fundamental risk level")

    # Technical Summary
    technical_signal: str = Field(description="Technical signal (bullish/bearish/neutral)")
    signal_strength: str = Field(description="Technical signal strength (strong/moderate/weak)")
    key_technical_indicators: List[str] = Field(description="Highlights from RSI, MACD, MA, OBV, etc.")
    entry_points: List[str] = Field(description="Suggested entry points")
    exit_strategies: List[str] = Field(description="Suggested exit points or strategies")
    stop_loss_recommendations: List[str] = Field(description="Stop loss recommendations")
    risk_level_technical: str = Field(description="Technical risk level")

    # Deep Research Summary
    innovation_level: str = Field(description="Level of innovation (High/Medium/Low)")
    market_position: str = Field(description="Project's market position and competition outlook")
    development_activity_score: Optional[int] = Field(description="Number of commits or contributors in last 90 days")
    tokenomics_summary: str = Field(description="Key insights from tokenomics")
    regulatory_status_summary: str = Field(description="Summary of compliance and jurisdictional clarity")
    community_sentiment: str = Field(description="Community engagement and sentiment overview")
    news_sentiment_summary: str = Field(description="Positive/Negative/Neutral media sentiment")

    # Risk Overview
    risk_summary: List[str] = Field(description="Summary of all identified risks across domains")
    risk_mitigation_strategies: List[str] = Field(description="Suggested ways to mitigate key risks")

    # Opportunity Highlights
    opportunity_highlights: List[str] = Field(description="Key opportunities and catalysts")
    roadmap_milestones: List[str] = Field(description="Upcoming milestones and their expected impact")
    potential_partnerships: List[str] = Field(description="Possible or rumored partnerships")

    # Comparative Analysis
    top_competitors: List[str] = Field(description="Top direct competitors")
    competitive_edge_summary: str = Field(description="How this project stands out vs competitors")

    # Analyst Thesis
    bull_case_summary: str = Field(description="Summary of bull case arguments")
    bear_case_summary: str = Field(description="Summary of bear case arguments")
    investment_thesis: str = Field(description="Final analyst view integrating all evidence")

    # Forecast Section (New)
    forecast_outlook: ForecastOutlook = Field(description="Forecasted future movement analysis")

    # Visual Links or References (Optional)
    supporting_links: List[str] = Field(default_factory=list, description="Links to charts, documents, or external resources")

### Secrets

class APIKeys(BaseModel):
    supertokens: SecretStr
    apify: SecretStr
    theagentic: SecretStr
    r2r: SecretStr
    openai: SecretStr
    app_smith: SecretStr
    sparkpost: SecretStr
    firecrawl: SecretStr
    logfire: SecretStr
    zeroentropy: Optional[SecretStr] = None
    coingecko: SecretStr
    jina_ai: SecretStr


class Database(BaseModel):
    postgres_connection_string: SecretStr

class SuperTokens(BaseModel):
    connection_uri: str
    email: str
    password: str
    app_name: str
    api_domain: str
    website_domain: str
    api_base_path: str
    website_base_path: str

class Android(BaseModel):
    client_id: SecretStr

class Ios(BaseModel):
    client_id: SecretStr

class Web(BaseModel):
    client_id: SecretStr

class GoogleAuth(BaseModel):
    android: Android
    ios: Ios
    web: Web

class TwitterAuth(BaseModel):
    client_id: SecretStr
    client_secret: SecretStr

class OpenTelemetryResourceAttributes(BaseModel):
    service_name: str

class OpenTelemetryExporter(BaseModel):
    protocol: str
    endpoint: str
    headers: Dict[str, str]

class OpenTelemetryConfig(BaseModel):
    resource_attributes: OpenTelemetryResourceAttributes
    exporter: OpenTelemetryExporter
    signoz_ingestion_key: SecretStr
    python_logging: Dict[str, bool]

class SwaggerDocs(BaseModel):
    username: str
    password: SecretStr

class Services(BaseModel):
    agentic_url: str

class AppConfig(BaseModel):
    model: str
    openai_model: str
    logfire_env: str
    allowed_origins: List[str]

class RapidApi(BaseModel):
    api_key: SecretStr
    host: str
    websearchhost: str
    websearchapi: SecretStr
    reddithost: str
    redditapi: SecretStr

class Coinbase(BaseModel):
    commerce_api_key: SecretStr
    commerce_webhook_secret: SecretStr

class Stripe(BaseModel):
    api_key: SecretStr
    webhook_secret: SecretStr
    subscription_price_id: SecretStr

class Settings(BaseModel):
    api_keys: APIKeys
    database: Database
    supertokens: SuperTokens
    google_auth: GoogleAuth
    twitter_auth: TwitterAuth
    opentelemetry: OpenTelemetryConfig
    swagger_docs: SwaggerDocs
    services: Services
    app_config: AppConfig
    rapid_api: RapidApi
    coinbase: Coinbase
    stripe: Stripe