import json
from pathlib import Path
import os
from ..config import Config
from typing import Optional, Dict, List
from msgraph.generated.models.message import Message
from ..core.logger import logger
from core_logging.client import EventType, LogLevel

class EmailProcessorService:
    def __init__(self, graph_client=None):
        self.assets_path = Config.ASSETS_PATH
        self.unmatched_trades_path = os.path.join(self.assets_path, 'unmatched_trades.json')
        self.graph_client = graph_client
        self.user_email = Config.USER_EMAIL

        # Get parameters from environment variables
        self.my_entity = os.environ.get('MY_ENTITY')
        
        logger.info(
            "Initializing Email Processor Service",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            data={"assets_path": self.assets_path},
            tags=["initialization", "service"]
        )
        
        self.load_unmatched_trades()

    def load_unmatched_trades(self):
        try:
            logger.info(
                "Loading unmatched trades data",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"path": self.unmatched_trades_path},
                tags=["data", "loading"]
            )
            
            with open(self.unmatched_trades_path, 'r', encoding='utf-8') as f:
                self.unmatched_trades = json.load(f)
                
            logger.info(
                f"Loaded {len(self.unmatched_trades)} unmatched trades",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"count": len(self.unmatched_trades)},
                tags=["data", "trades", "success"]
            )
        except Exception as e:
            logger.log_exception(
                e,
                message="Error loading unmatched trades",
                entity=self.my_entity,
                user_id="system",
                data={"path": self.unmatched_trades_path},
                tags=["error", "data", "loading"]
            )
            self.unmatched_trades = []
            logger.warning(
                "Initialized with empty unmatched trades list due to error",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["data", "fallback"]
            )

    async def process_email_result(self, email_obj, llm_response: str) -> Dict:
        """Process the LLM's response about an email"""
        try:
            logger.info(
                "Processing LLM response for email",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_id": email_obj.id if hasattr(email_obj, 'id') else None,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None
                },
                tags=["llm", "processing"]
            )
            
            # Parse the LLM response into JSON
            llm_data = json.loads(llm_response)
            
            # Check if this is a confirmation email
            is_confirmation = llm_data["Email"]["Confirmation"].lower() == "yes"
            
            if not is_confirmation:
                logger.info(
                    "Email identified as not a confirmation email",
                    event_type=EventType.SYSTEM_EVENT,
                    entity=self.my_entity,
                    user_id="system",
                    data={
                        "email_subject": llm_data["Email"].get("Email_subject"),
                        "email_sender": llm_data["Email"].get("Email_sender")
                    },
                    tags=["email", "not_confirmation"]
                )
                
                await self.mark_email_unread(email_obj)
                return {
                    "is_confirmation": False,
                    "identified_trade_details": None
                }
            
            # Process each trade mentioned in the email
            identified_trade_details = []
            trades_count = 0
            
            logger.info(
                f"Email identified as confirmation with {len(llm_data.get('Trades', []))} trades mentioned",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_subject": llm_data["Email"].get("Email_subject"),
                    "trades_count": len(llm_data.get("Trades", []))
                },
                tags=["email", "confirmation"]
            )
            
            for trade in llm_data.get("Trades", []):
                trades_count += 1
                trade_number = trade.get("TradeNumber")
                
                if not trade_number:
                    logger.warning(
                        "Trade mentioned in email but no trade number found",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"trade_data": trade},
                        tags=["trade", "missing_id"]
                    )
                    continue
                    
                logger.info(
                    f"Processing trade reference: {trade_number}",
                    event_type=EventType.SYSTEM_EVENT,
                    entity=self.my_entity,
                    user_id="system",
                    data={"trade_number": trade_number},
                    tags=["trade", "processing"]
                )
                
                confirmation_ok = trade.get("Confirmation_OK", "").lower() == "yes"
                
                # Look up the trade details
                details = self.get_trade_details(trade_number)
                if details:
                    logger.info(
                        f"Found trade {trade_number} in unmatched trades data",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"trade_number": trade_number, "confirmation_ok": confirmation_ok},
                        tags=["trade", "found"]
                    )
                    
                    details["confirmation_ok"] = confirmation_ok
                    identified_trade_details.append(details)
                else:
                    logger.warning(
                        f"Trade {trade_number} not found in unmatched trades data",
                        event_type=EventType.SYSTEM_EVENT,
                        entity=self.my_entity,
                        user_id="system",
                        data={"trade_number": trade_number},
                        tags=["trade", "not_found"]
                    )
            
            result = {
                "is_confirmation": True,
                "email_details": llm_data["Email"],
                "email_trade_details": llm_data.get("Trades", []),
                "identified_trade_details": identified_trade_details
            }
            
            logger.info(
                f"Successfully processed email with {len(identified_trade_details)} identified trades",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={
                    "trades_total": trades_count,
                    "trades_identified": len(identified_trade_details)
                },
                tags=["email", "processing", "success"]
            )
            
            return result
            
        except json.JSONDecodeError as e:
            logger.log_exception(
                e,
                message="Error parsing LLM response JSON",
                entity=self.my_entity,
                user_id="system",
                data={"response_length": len(llm_response)},
                tags=["llm", "json", "error"]
            )
            return {
                "is_confirmation": False,
                "trade_details": None,
                "error": "Invalid LLM response format"
            }
        except Exception as e:
            logger.log_exception(
                e,
                message="Error processing email result",
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_id": email_obj.id if hasattr(email_obj, 'id') else None,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None
                },
                tags=["email", "processing", "error"]
            )
            return {
                "is_confirmation": False,
                "trade_details": None,
                "error": str(e)
            }

    async def mark_email_unread(self, email_obj):
        """Mark an email as unread using Microsoft Graph API"""
        try:
            if not self.graph_client:
                raise ValueError("Graph client not initialized")
            if not self.user_email:
                raise ValueError("User email not initialized")
            
            logger.info(
                f"Marking email as unread: {email_obj.subject if hasattr(email_obj, 'subject') else 'Unknown'}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"email_id": email_obj.id if hasattr(email_obj, 'id') else None},
                tags=["email", "status", "unread"]
            )
            
            update = Message()
            update.is_read = False
            await self.graph_client.users.by_user_id(self.user_email).messages.by_message_id(email_obj.id).patch(body=update)
            
            logger.info(
                f"Successfully marked email as unread",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={"email_id": email_obj.id},
                tags=["email", "status", "success"]
            )
        except Exception as e:
            logger.log_exception(
                e,
                message="Error marking email as unread",
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_id": email_obj.id if hasattr(email_obj, 'id') else None,
                    "email_type": type(email_obj).__name__
                },
                tags=["email", "status", "error"]
            )

    async def move_email_to_folder(self, email_obj, folder_path):
        """Move an email to a different folder using Microsoft Graph API"""
        try:
            if not self.graph_client:
                raise ValueError("Graph client not initialized")
            if not self.user_email:
                raise ValueError("User email not initialized")
            
            logger.info(
                f"Moving email to folder: {folder_path}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_id": email_obj.id if hasattr(email_obj, 'id') else None,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None,
                    "folder_path": folder_path
                },
                tags=["email", "folder", "move"]
            )
            
            # First, we need to get the folder ID from the folder path
            folder_id = await self.get_folder_id_by_path(folder_path)
            if not folder_id:
                error_msg = f"Could not find folder: {folder_path}"
                logger.error(
                    error_msg,
                    event_type=EventType.SYSTEM_EVENT,
                    entity=self.my_entity,
                    user_id="system",
                    data={"folder_path": folder_path},
                    tags=["email", "folder", "error"]
                )
                raise ValueError(error_msg)
                
            # Import the correct model from the newer SDK
            from msgraph.generated.users.item.messages.item.move.move_post_request_body import MovePostRequestBody
            
            # Create the request body using the model
            request_body = MovePostRequestBody(
                destination_id = folder_id
            )
            
            # Call the move API
            result = await self.graph_client.users.by_user_id(self.user_email).messages.by_message_id(email_obj.id).move.post(request_body)
            
            logger.info(
                f"Successfully moved email to folder {folder_path}",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                data={
                    "email_id": email_obj.id,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None,
                    "folder_path": folder_path
                },
                tags=["email", "folder", "success"]
            )
            
            return result
        except Exception as e:
           logger.log_exception(
               e,
               message="Error moving email to folder",
               entity=self.my_entity,
               user_id="system",
               data={
                   "email_id": email_obj.id if hasattr(email_obj, 'id') else None,
                   "folder_path": folder_path
               },
               tags=["email", "folder", "error"]
           )
           return None

    async def get_folder_id_by_path(self, folder_path):
       """Get the folder ID for a given folder path"""
       try:
           logger.info(
               f"Looking up folder ID for path: {folder_path}",
               event_type=EventType.SYSTEM_EVENT,
               entity=self.my_entity,
               user_id="system",
               data={"folder_path": folder_path},
               tags=["email", "folder", "lookup"]
           )
           
           # Split the path into components
           path_components = folder_path.split('/')
           
           # Start with the root folder (Inbox)
           current_folder = path_components[0]
           current_id = None
           
           # First get the ID of the first component (usually Inbox)
           folders = await self.graph_client.users.by_user_id(self.user_email).mail_folders.get()
           for folder in folders.value:
               if folder.display_name.lower() == current_folder.lower():
                   current_id = folder.id
                   break
                   
           if not current_id:
               logger.error(
                   f"Could not find root folder: {current_folder}",
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"folder": current_folder},
                   tags=["email", "folder", "error"]
               )
               return None
               
           # Navigate through the rest of the path
           for i in range(1, len(path_components)):
               folder_name = path_components[i]
               found = False
               
               logger.info(
                   f"Looking for subfolder: {folder_name}",
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"folder": folder_name, "parent_id": current_id},
                   tags=["email", "folder", "lookup"]
               )
               
               # Get child folders
               child_folders = await self.graph_client.users.by_user_id(self.user_email).mail_folders.by_mail_folder_id(current_id).child_folders.get()
               
               for folder in child_folders.value:
                   if folder.display_name.lower() == folder_name.lower():
                       current_id = folder.id
                       found = True
                       break
                       
               if not found:
                   logger.error(
                       f"Could not find subfolder: {folder_name}",
                       event_type=EventType.SYSTEM_EVENT,
                       entity=self.my_entity,
                       user_id="system",
                       data={"folder": folder_name, "parent_id": current_id},
                       tags=["email", "folder", "error"]
                   )
                   return None
           
           logger.info(
               f"Found folder ID: {current_id} for path: {folder_path}",
               event_type=EventType.SYSTEM_EVENT,
               entity=self.my_entity,
               user_id="system",
               data={"folder_id": current_id, "folder_path": folder_path},
               tags=["email", "folder", "success"]
           )
           return current_id
       
       except Exception as e:
           logger.log_exception(
               e,
               message=f"Error getting folder ID by path",
               entity=self.my_entity,
               user_id="system",
               data={"folder_path": folder_path},
               tags=["email", "folder", "error"]
           )
           return None

    def get_trade_details(self, trade_number: str) -> Optional[Dict]:
       """Get the details of a trade from unmatched_trades.json"""
       try:
           for trade in self.unmatched_trades:
               if str(trade.get('TradeNumber')) == str(trade_number):
                   logger.info(
                       f"Found trade details for trade number: {trade_number}",
                       event_type=EventType.SYSTEM_EVENT,
                       entity=self.my_entity,
                       user_id="system",
                       data={"trade_number": trade_number},
                       tags=["trade", "lookup", "success"]
                   )
                   return trade
                   
           logger.info(
               f"No trade details found for trade number: {trade_number}",
               event_type=EventType.SYSTEM_EVENT,
               entity=self.my_entity,
               user_id="system",
               data={"trade_number": trade_number},
               tags=["trade", "lookup", "not_found"]
           )
           return None
       except Exception as e:
           logger.log_exception(
               e,
               message=f"Error looking up trade details",
               entity=self.my_entity,
               user_id="system",
               data={"trade_number": trade_number},
               tags=["trade", "lookup", "error"]
           )
           return None
       
    def update_email_status(self, email_id, status):
       """Update email status in email_matches.json"""
       try:
           logger.info(
               f"Updating email status to '{status}'",
               event_type=EventType.DATA_CHANGE,
               entity=self.my_entity,
               user_id="system",
               data={"email_id": email_id, "status": status},
               tags=["email", "status", "update"]
           )
           
           email_matches_file = os.path.join(self.assets_path, 'email_matches.json')
           
           if not os.path.exists(email_matches_file):
               error_msg = "Email matches file not found"
               logger.error(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"path": email_matches_file},
                   tags=["email", "file", "error"]
               )
               return {"success": False, "message": error_msg}
           
           with open(email_matches_file, 'r', encoding='utf-8') as f:
               email_matches = json.load(f)
           
           found = False
           for email in email_matches:
               if email.get("InferredTradeID") == email_id:
                   # Store previous status before updating
                   email["previous_status"] = email.get("status", "")
                   email["status"] = status
                   found = True
                   break
           
           if found:
               logger.info(
                   f"Updated email status to '{status}'",
                   event_type=EventType.DATA_CHANGE,
                   entity=self.my_entity,
                   user_id="system",
                   data={
                       "email_id": email_id, 
                       "status": status,
                       "previous_status": email.get("previous_status", "")
                   },
                   tags=["email", "status", "success"]
               )
           else:
               error_msg = f"Email with ID {email_id} not found"
               logger.warning(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"email_id": email_id},
                   tags=["email", "status", "not_found"]
               )
               return {"success": False, "message": error_msg}
           
           with open(email_matches_file, 'w', encoding='utf-8') as f:
               json.dump(email_matches, f, indent=2, ensure_ascii=False)
           
           return {"success": True, "message": f"Email status updated to {status}"}
       
       except Exception as e:
           logger.log_exception(
               e,
               message=f"Error updating email status",
               entity=self.my_entity,
               user_id="system",
               data={"email_id": email_id, "status": status},
               tags=["email", "status", "error"]
           )
           
           return {"success": False, "message": f"Error updating email status: {str(e)}"}
   
    def undo_status_change(self, email_id):
       """Revert to previous email status"""
       try:
           logger.info(
               f"Undoing status change for email",
               event_type=EventType.DATA_CHANGE,
               entity=self.my_entity,
               user_id="system",
               data={"email_id": email_id},
               tags=["email", "status", "undo"]
           )
           
           email_matches_file = os.path.join(self.assets_path, 'email_matches.json')
           
           if not os.path.exists(email_matches_file):
               error_msg = "Email matches file not found"
               logger.error(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"path": email_matches_file},
                   tags=["email", "file", "error"]
               )
               return {"success": False, "message": error_msg}
           
           with open(email_matches_file, 'r', encoding='utf-8') as f:
               email_matches = json.load(f)
           
           found = False
           previous_status = None
           for email in email_matches:
               if email.get("InferredTradeID") == email_id:
                   if "previous_status" in email:
                       previous_status = email["previous_status"]
                       email["status"] = previous_status
                       found = True
                   else:
                       error_msg = "No previous status found to undo"
                       logger.warning(
                           error_msg,
                           event_type=EventType.SYSTEM_EVENT,
                           entity=self.my_entity,
                           user_id="system",
                           data={"email_id": email_id},
                           tags=["email", "status", "no_previous"]
                       )
                       return {"success": False, "message": error_msg}
                   break
           
           if not found:
               error_msg = f"Email with ID {email_id} not found"
               logger.warning(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"email_id": email_id},
                   tags=["email", "status", "not_found"]
               )
               return {"success": False, "message": error_msg}
           
           with open(email_matches_file, 'w', encoding='utf-8') as f:
               json.dump(email_matches, f, indent=2, ensure_ascii=False)
           
           logger.info(
               f"Successfully reverted email status to '{previous_status}'",
               event_type=EventType.DATA_CHANGE,
               entity=self.my_entity,
               user_id="system",
               data={"email_id": email_id, "status": previous_status},
               tags=["email", "status", "success"]
           )
           
           return {"success": True, "message": f"Status reverted to {previous_status}"}
       
       except Exception as e:
           logger.log_exception(
               e,
               message=f"Error undoing status change",
               entity=self.my_entity,
               user_id="system",
               data={"email_id": email_id},
               tags=["email", "status", "error"]
           )
           return {"success": False, "message": f"Error undoing status change: {str(e)}"}
   
    def clear_json_file(self, file_type):
       """Clear JSON file contents"""
       try:
           logger.info(
               f"Clearing JSON file: {file_type}",
               event_type=EventType.DATA_CHANGE,
               entity=self.my_entity,
               user_id="system",
               data={"file_type": file_type},
               tags=["file", "clear"]
           )
           
           if file_type == 'email_matches':
               file_path = os.path.join(self.assets_path, 'email_matches.json')
               file_name = 'email_matches.json'
           elif file_type == 'matched_trades':
               file_path = os.path.join(self.assets_path, 'matched_trades.json')
               file_name = 'matched_trades.json'
           else:
               error_msg = f"Invalid file type: {file_type}"
               logger.error(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"file_type": file_type},
                   tags=["file", "invalid"]
               )
               return {"success": False, "message": error_msg}
           
           if not os.path.exists(file_path):
               error_msg = f"{file_name} not found"
               logger.error(
                   error_msg,
                   event_type=EventType.SYSTEM_EVENT,
                   entity=self.my_entity,
                   user_id="system",
                   data={"file_path": file_path},
                   tags=["file", "not_found"]
               )
               return {"success": False, "message": error_msg}
           
           with open(file_path, 'w', encoding='utf-8') as f:
               f.write('[]')
           
           logger.info(
               f"Successfully cleared {file_name}",
               event_type=EventType.DATA_CHANGE,
               entity=self.my_entity,
               user_id="system",
               data={"file_name": file_name},
               tags=["file", "clear", "success"]
           )
           
           return {"success": True, "message": f"Successfully cleared {file_name}"}
       
       except Exception as e:
           logger.log_exception(
               e,
               message=f"Error clearing JSON file",
               entity=self.my_entity,
               user_id="system",
               data={"file_type": file_type},
               tags=["file", "clear", "error"]
           )
           return {"success": False, "message": f"Error clearing {file_type}: {str(e)}"}