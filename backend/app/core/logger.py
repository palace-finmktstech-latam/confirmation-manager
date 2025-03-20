from core_logging.client import LogClient, EventType, LogLevel

# Initialize the logger
logger = LogClient(
    app_name="Confirmation Manager",
    api_url="http://localhost:8001/api/",
    default_source="confirmation_manager"
)