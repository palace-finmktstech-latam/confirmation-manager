# backend/app/main.py
import asyncio
from flask import Flask
from . import create_app
from .config import Config
from .services.email_processor_service import EmailProcessorService
from .services.llm_service import LLMService
from .services.confirmation_service import ConfirmationService
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
import threading
from .core.logger import logger
from core_logging.client import EventType, LogLevel

# Create the Flask app
app = create_app()

def get_graph_client():
    credentials = ClientSecretCredential(
        tenant_id=Config.GRAPH_TENANT_ID,
        client_id=Config.GRAPH_CLIENT_ID,
        client_secret=Config.GRAPH_CLIENT_SECRET
    )
    return GraphServiceClient(credentials=credentials)

async def monitor_outlook_emails():
    """Start monitoring Outlook folder for new emails"""
    from .services.outlook_monitor_service import OutlookMonitorService
    
    user_email = Config.USER_EMAIL
    graph_client = get_graph_client()
    
    logger.info(
        "Initializing email monitoring services",
        event_type=EventType.SYSTEM_EVENT,
        user_id="system",
        entity="Banco ABC",
        tags=["startup", "monitoring"]
    )
    
    # Create services
    email_processor = EmailProcessorService(graph_client=graph_client)
    llm_service = LLMService(graph_client=graph_client)
    confirmation_service = ConfirmationService(
        graph_client=graph_client,
        llm_service=llm_service,
        email_processor_service=email_processor,
        logger=logger  # Pass logger to confirmation service
    )
    
    # Create and configure the monitor
    monitor = OutlookMonitorService(user_email, graph_client)
    
    # Register event handler
    monitor.register_event_handler("new_unread_email", 
    lambda emails: asyncio.create_task(confirmation_service.handle_new_unread_email(emails)))

    logger.info(
        f"Starting email monitoring for {user_email}",
        event_type=EventType.SYSTEM_EVENT,
        user_id="system",
        entity="Banco ABC",
        data={"folder": "Inbox/Confirmations", "check_interval": 10},
        tags=["startup", "monitoring"]
    )
    
    # Start monitoring
    await monitor.monitor_folder("Inbox/Confirmations", check_interval=10)

def start_email_monitor():
    """Run the email monitor in a separate thread"""
    try:
        print("Email monitor thread started")
        # Force explicit stdout flush to ensure visibility
        import sys
        sys.stdout.flush()
        
        # Load modules just to verify they're working
        print(f"Logger initialized: {logger is not None}")
        print(f"Config USER_EMAIL: {Config.USER_EMAIL}")
        sys.stdout.flush()
        
        asyncio.run(monitor_outlook_emails())
    except Exception as e:
        print(f"CRITICAL ERROR in email monitor: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        
        logger.log_exception(
            e,
            message="Error in email monitor",
            entity="Banco ABC",
            user_id="system",
            tags=["error", "monitoring"]
        )

# Start the email monitor in a separate thread when the app starts
if __name__ == "__main__":
    try:
        logger.info(
            "Starting Confirmation Manager",
            event_type=EventType.SYSTEM_EVENT,
            user_id="system",
            entity="Banco ABC",
            tags=["startup"]
        )
        
        # Start email monitoring in a background thread
        monitor_thread = threading.Thread(target=start_email_monitor)
        monitor_thread.daemon = True
        monitor_thread.start()
        
        # Start Flask app
        app.run(host='0.0.0.0', port=5005, debug=True)
    except Exception as e:
        logger.log_exception(
            e,
            message="Fatal error in Confirmation Manager",
            entity="Banco ABC",
            user_id="system",
            level=LogLevel.CRITICAL,
            tags=["error", "fatal"]
        )
        logger.flush()
        logger.shutdown()