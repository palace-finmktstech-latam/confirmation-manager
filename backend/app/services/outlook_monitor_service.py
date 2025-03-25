# backend/app/services/outlook_monitor_service.py
import os
from ..core.logger import logger
from core_logging.client import EventType, LogLevel
from email_monitoring import OutlookMonitor, EmailProcessor

class OutlookMonitorService:
    def __init__(self, user_email, graph_client):
        self.user_email = user_email
        self.my_entity = os.environ.get('MY_ENTITY')
        
        # Use the core monitoring package
        self.monitor = OutlookMonitor(
            user_email=user_email,
            graph_client=graph_client,
            logger=logger,
            entity=self.my_entity,
            user_id="system"
        )
        
        # Create an email processor for attachments
        self.email_processor = EmailProcessor(logger=logger)
        
        logger.info(
            f"Initialized Outlook Monitor for {user_email}",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            tags=["monitoring", "initialization"]
        )
    
    def register_event_handler(self, event_name, handler):
        """Register an event handler"""
        self.monitor.register_event_handler(event_name, handler)
        logger.info(
            f"Registered event handler for '{event_name}'",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            tags=["monitoring", "event_handler"]
        )

    async def monitor_folder(self, folder_name="Inbox", check_interval=60):
        """Start monitoring the specified folder"""
        # The core package handles all the monitoring logic
        await self.monitor.monitor_folder(folder_name, check_interval)

    async def process_message(self, message):
        """Process a message - this is called by the monitor"""
        # The monitor's process_message method will call our custom one via event handler
        await self.monitor.process_message(message)

    async def mark_as_read(self, message_id):
        """Mark a message as read"""
        # Delegate to the core package
        await self.monitor.mark_as_read(message_id)