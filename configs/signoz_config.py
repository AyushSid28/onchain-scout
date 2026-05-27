import logging
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from configs.config import get_settings

settings =get_settings()

resource = Resource.create({
        "service.name": settings.opentelemetry.resource_attributes.service_name
    })

logger_provider = LoggerProvider(resource=resource)
log_exporter = OTLPLogExporter(
    endpoint=settings.opentelemetry.exporter.endpoint,
    headers={
        "signoz-access-token": settings.opentelemetry.signoz_ingestion_key.get_secret_value()
    }
)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
otlp_handler = LoggingHandler(level=logging.DEBUG, logger_provider=logger_provider)

# Create formatter for console logs
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def setup_logger(name: str):
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Clear any existing handlers
    logger.handlers.clear()
    # Add console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    logger.addHandler(otlp_handler)
    # Prevent propagation to avoid duplicate logs
    logger.propagate = False
    return logger

def setup_telemetry(app):

    # Initialize tracer provider with resource
    tracer_provider = TracerProvider(resource=resource)

    # Configure OTLP exporter
    otlp_exporter = OTLPSpanExporter(
        endpoint=settings.opentelemetry.exporter.endpoint,
        headers={
            "signoz-access-token": settings.opentelemetry.signoz_ingestion_key.get_secret_value()
        }
    )

    # Add span processor
    span_processor = BatchSpanProcessor(otlp_exporter)
    tracer_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(tracer_provider)

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)
    RequestsInstrumentor().instrument()
    LoggingInstrumentor().instrument()