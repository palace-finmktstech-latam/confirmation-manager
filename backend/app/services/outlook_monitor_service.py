# backend/app/services/outlook_monitor_service.py
import logging
from datetime import datetime, UTC
from msgraph.generated.users.item.mail_folders.item.messages.messages_request_builder import MessagesRequestBuilder
import os
import asyncio
import json
from msgraph.generated.models.message import Message
from bs4 import BeautifulSoup
import io
from PyPDF2 import PdfReader
import base64
from ..core.logger import logger
from core_logging.client import EventType, LogLevel

class EventDispatcher:
    def __init__(self):
        self.handlers = {}
        
    def register(self, event_name, handler):
        self.handlers[event_name] = handler
        
    async def dispatch(self, event_name, *args, **kwargs):
        handler = self.handlers.get(event_name)
        if handler:
            if asyncio.iscoroutinefunction(handler):
                await handler(*args, **kwargs)
            else:
                result = handler(*args, **kwargs)
                if asyncio.iscoroutine(result):
                    await result

class OutlookMonitorService:
    def __init__(self, user_email, graph_client):
        self.user_email = user_email
        self.client = graph_client
        self.event_dispatcher = EventDispatcher()
        self._setup_logging()

        # Get parameters from environment variables
        self.my_entity = os.environ.get('MY_ENTITY')
        
        logger.info(
            f"Initialized Outlook Monitor for {user_email}",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            tags=["monitoring", "initialization"]
        )

    def _setup_logging(self):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('email_monitor.log'),
                logging.StreamHandler()
            ]
        )
        
    def register_event_handler(self, event_name, handler):
        """Register an event handler"""
        self.event_dispatcher.register(event_name, handler)
        logger.info(
            f"Registered event handler for '{event_name}'",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            tags=["monitoring", "event_handler"]
        )

    async def get_folder_id(self, folder_path):
        try:
            logger.info(
                f"Getting folder ID for path: {folder_path}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"folder_path": folder_path},
                tags=["outlook", "folder"]
            )
            
            path_parts = folder_path.split('/')
            current_folder_id = None
            current_folders = await self.client.users.by_user_id(self.user_email).mail_folders.get()

            for part in path_parts:
                found = False
                for folder in current_folders.value:
                    if folder.display_name.lower() == part.lower():
                        current_folder_id = folder.id
                        current_folders = await self.client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id(current_folder_id).child_folders.get()
                        found = True
                        break

                if not found:
                    error_msg = f"Could not find folder part '{part}' in path '{folder_path}'"
                    logger.error(
                        error_msg,
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"folder_path": folder_path, "missing_part": part},
                        tags=["outlook", "folder", "error"]
                    )
                    raise ValueError(error_msg)

            logger.info(
                f"Found folder ID: {current_folder_id} for path: {folder_path}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"folder_id": current_folder_id},
                tags=["outlook", "folder", "success"]
            )
            return current_folder_id

        except Exception as e:
            logger.log_exception(
                e,
                message=f"Error finding folder ID for path: {folder_path}",
                entity=self.my_entity,
                user_id="system",
                data={"folder_path": folder_path},
                tags=["outlook", "folder", "error"]
            )
            raise

    async def monitor_folder(self, folder_name="Inbox", check_interval=60):
        logger.info(
            f"Starting monitoring of folder: {folder_name}",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            data={"folder_name": folder_name, "check_interval": check_interval},
            tags=["monitoring", "start"]
        )

        try:
            folder_id = await self.get_folder_id(folder_name)
            logger.info(
                f"Found folder ID: {folder_id}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"folder_id": folder_id, "folder_name": folder_name},
                tags=["monitoring", "folder"]
            )

            while True:
                try:
                    logger.info(
                        f"Checking folder {folder_name} for new messages",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        tags=["monitoring", "check"]
                    )
                    
                    # Get first page of messages
                    messages_response = await self.client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id(folder_id).messages.get()
                    
                    # Initialize all_messages with first page
                    all_messages = list(messages_response.value)
                    
                    # Process additional pages if they exist
                    next_link = getattr(messages_response, 'odata_next_link', None)
                    while next_link:
                        # Create a new request with the next link URL
                        next_request = self.client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id(folder_id).messages.with_url(next_link)
                        messages_response = await next_request.get()
                        all_messages.extend(messages_response.value)
                        next_link = getattr(messages_response, 'odata_next_link', None)
                    
                    logger.info(
                        f"Retrieved {len(all_messages)} messages from folder {folder_name}",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"count": len(all_messages), "folder_name": folder_name},
                        tags=["monitoring", "messages"]
                    )

                    new_unread_messages = [message for message in all_messages if not message.is_read]
                    
                    if new_unread_messages:
                        logger.info(
                            f"Found {len(new_unread_messages)} new unread messages",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            data={"count": len(new_unread_messages)},
                            tags=["monitoring", "unread"]
                        )
                        
                        processed_messages = []
                        for message in new_unread_messages:
                            # Get the full message details
                            full_message = await self.client.users.by_user_id(self.user_email).messages.by_message_id(message.id).get()
                            await self.process_message(full_message)
                            processed_messages.append(full_message)
                        
                        logger.info(
                            f"Dispatching {len(processed_messages)} messages to event handlers",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            data={"count": len(processed_messages)},
                            tags=["monitoring", "dispatch"]
                        )
                        
                        await self.event_dispatcher.dispatch("new_unread_email", processed_messages)
                    else:
                        logger.info(
                            "No new unread messages found",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            tags=["monitoring", "check"]
                        )

                    await asyncio.sleep(check_interval)

                except Exception as e:
                    logger.log_exception(
                        e,
                        message=f"Error monitoring folder: {folder_name}",
                        entity=self.my_entity,
                        user_id="system",
                        data={"folder_name": folder_name},
                        tags=["monitoring", "error"]
                    )
                    await asyncio.sleep(check_interval)
        except Exception as e:
            logger.log_exception(
                e,
                message=f"Fatal error initializing folder monitoring",
                entity=self.my_entity,
                user_id="system",
                level=LogLevel.CRITICAL,
                data={"folder_name": folder_name},
                tags=["monitoring", "fatal"]
            )
            raise

    async def process_message(self, message):
        try:
            logger.info(
                f"Processing message: {message.subject}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={
                    "subject": message.subject,
                    "id": message.id,
                    "sender": message.sender.email_address.address if message.sender and hasattr(message.sender, 'email_address') else "Unknown"
                },
                tags=["email", "processing"]
            )
            
            # Fetch attachments explicitly
            attachments_response = await self.client.users.by_user_id(self.user_email).messages.by_message_id(message.id).attachments.get()
            
            # For each attachment, fetch its content if it's a PDF
            processed_attachments = []
            
            logger.info(
                f"Found {len(attachments_response.value)} attachments",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"count": len(attachments_response.value), "message_id": message.id},
                tags=["email", "attachments"]
            )
            
            for attachment in attachments_response.value:
                if attachment.content_type == "application/pdf":
                    logger.info(
                        f"Processing PDF attachment: {attachment.name}",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"name": attachment.name, "id": attachment.id},
                        tags=["email", "attachment", "pdf"]
                    )
                    
                    full_attachment = await self.client.users.by_user_id(self.user_email).messages.by_message_id(message.id).attachments.by_attachment_id(attachment.id).get()
                    
                    # Process PDF content
                    try:
                        pdf_bytes = full_attachment.content_bytes
                        logger.info(
                            f"Raw PDF size: {len(pdf_bytes)} bytes",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            data={"size": len(pdf_bytes), "name": attachment.name},
                            tags=["email", "pdf", "processing"]
                        )
                        
                        # Convert bytes to string if needed
                        if isinstance(pdf_bytes, bytes):
                            pdf_base64 = pdf_bytes.decode('utf-8')
                        else:
                            pdf_base64 = pdf_bytes
                            
                        # Decode base64
                        padding = len(pdf_base64) % 4
                        if padding:
                            pdf_base64 += '=' * (4 - padding)
                            
                        pdf_decoded = base64.b64decode(pdf_base64)
                        
                        # Create PDF reader with decoded content
                        pdf = PdfReader(io.BytesIO(pdf_decoded))
                        
                        logger.info(
                            f"PDF processed: {len(pdf.pages)} pages",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            data={"pages": len(pdf.pages), "name": attachment.name},
                            tags=["email", "pdf", "extraction"]
                        )
                        
                        # Extract text
                        pdf_text = ""
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            pdf_text += page_text + "\n"
                        
                        # Store the decoded content and extracted text in the attachment
                        full_attachment.decoded_content = pdf_decoded
                        full_attachment.extracted_text = pdf_text
                        
                        logger.info(
                            f"Successfully extracted text from PDF",
                            event_type=EventType.SYSTEM_EVENT,
                            entity=self.my_entity,
                            user_id="system",
                            data={"name": attachment.name, "text_length": len(pdf_text)},
                            tags=["email", "pdf", "success"]
                        )
                        
                    except Exception as e:
                        logger.log_exception(
                            e,
                            message=f"Error processing PDF {full_attachment.name}",
                            entity=self.my_entity,
                            user_id="system",
                            data={"name": attachment.name},
                            tags=["email", "pdf", "error"]
                        )
                    
                    processed_attachments.append(full_attachment)
                else:
                    logger.info(
                        f"Non-PDF attachment: {attachment.name} ({attachment.content_type})",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"name": attachment.name, "type": attachment.content_type},
                        tags=["email", "attachment"]
                    )
                    processed_attachments.append(attachment)
            
            message.attachments = processed_attachments
            
            # Extract all message details
            message_details = {
                "message_id": message.id,
                "processed_time": datetime.now(UTC).isoformat(),
                "subject": message.subject,
                "sender_email": message.sender.email_address.address,
                "sender_name": message.sender.email_address.name,
                "received_date": message.received_date_time.date().isoformat(),
                "received_time": message.received_date_time.time().isoformat(),
                "body_content": BeautifulSoup(message.body.content, "html.parser").get_text() if message.body else "No body content",
                "attachments": []
            }
            
            # Process attachments
            for attachment in message.attachments:
                if attachment.content_type == "application/pdf":
                    attachment_info = {
                        "name": attachment.name,
                        "type": attachment.content_type,
                        "content": attachment.extracted_text[:1000] if hasattr(attachment, 'extracted_text') else "No text extracted"
                    }
                else:
                    attachment_info = {
                        "name": attachment.name,
                        "type": attachment.content_type,
                        "content": "Non-PDF attachment"
                    }
                message_details["attachments"].append(attachment_info)
            
            # Store the details in the message object
            message.processed_details = message_details
            
            # Save audit record
            self._save_audit_record(message_details)
            
            await self.mark_as_read(message.id)
            
            logger.info(
                f"Successfully processed message: {message.subject}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"id": message.id, "subject": message.subject},
                tags=["email", "processing", "success"]
            )
            
        except Exception as e:
            logger.log_exception(
                e,
                message=f"Error processing message {message.id if hasattr(message, 'id') else 'unknown'}",
                entity=self.my_entity,
                user_id="system",
                data={"subject": message.subject if hasattr(message, 'subject') else "unknown"},
                tags=["email", "processing", "error"]
            )

    async def mark_as_read(self, message_id):
        try:
            logger.info(
                f"Marking message {message_id} as read",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"message_id": message_id},
                tags=["email", "status"]
            )
            
            update = Message()
            update.is_read = True
            await self.client.users.by_user_id(self.user_email).messages.by_message_id(message_id).patch(body=update)
            
            logger.info(
                f"Successfully marked message {message_id} as read",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"message_id": message_id},
                tags=["email", "status", "success"]
            )
        except Exception as e:
            logger.log_exception(
                e,
                message=f"Error marking message as read",
                entity=self.my_entity,
                user_id="system",
                data={"message_id": message_id},
                tags=["email", "status", "error"]
            )
            raise

    def _save_audit_record(self, audit_record):
        try:
            with open('email_audit.json', 'a') as f:
                json.dump(audit_record, f)
                f.write('\n')
                
            logger.info(
                f"Saved audit record for message: {audit_record.get('subject', 'unknown')}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"message_id": audit_record.get('message_id')},
                tags=["audit", "email"]
            )
        except Exception as e:
            logger.log_exception(
                e,
                message=f"Error saving audit record",
                entity=self.my_entity,
                user_id="system",
                data={"message_id": audit_record.get('message_id', 'unknown')},
                tags=["audit", "error"]
            )