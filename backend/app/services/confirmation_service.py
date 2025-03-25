# backend/app/services/confirmation_service.py
import asyncio
import os
import logging
import json
from datetime import datetime, UTC
from ..config import Config
from ..core.logger import logger
from core_logging.client import EventType, LogLevel
from email_monitoring.utils import clean_html, extract_dates

class ConfirmationService:
    def __init__(self, graph_client=None, llm_service=None, email_processor_service=None, logger=None):
        self.graph_client = graph_client
        self.llm_service = llm_service
        self.email_processor = email_processor_service
        self.assets_path = Config.ASSETS_PATH
        self.logger = logger

        # Get parameters from environment variables
        self.my_entity = os.environ.get('MY_ENTITY')
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, Config.LOG_LEVEL),
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    def load_email_entities(self, file_name="email_entities.json"):
        try:
            # Use app-level data directory
            data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
            file_path = os.path.join(data_dir, file_name)
            
            if not os.path.exists(file_path):
                self.logger.error(f"Email entities file not found: {file_path}")
                return []
                
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load email entities: {str(e)}")
            return []

    def get_entity_info(self, sender_email, email_entities):
        """Get entity information from email"""
        for entity in email_entities:
            if 'email' in entity and entity['email'] == sender_email:
                return (
                    entity['entity_name'],
                    entity.get('entity_display_name', entity['entity_name']),
                    entity.get('client_id', 'No ID')
                )
        return None, None, None

    def save_identified_trade(self, trade_data: dict):
        """Save identified trade to matched_trades.json"""
        matches_file = os.path.join(self.assets_path, 'matched_trades.json')
        print(f"Saving trade data: {trade_data}")
        try:
            # Create file with empty list if it doesn't exist
            if not os.path.exists(matches_file):
                with open(matches_file, 'w', encoding='utf-8') as f:
                    f.write('[]')
            
            # Read existing matches
            with open(matches_file, 'r', encoding='utf-8') as f:
                matches = json.load(f)
            
            # Add timestamp to trade data
            trade_data['identified_at'] = datetime.now(UTC).isoformat()
            
            # Append new match
            matches.append(trade_data)
            
            # Write back to file
            with open(matches_file, 'w', encoding='utf-8') as f:
                json.dump(matches, f, indent=2, ensure_ascii=False)
                
            trade_number = trade_data.get('TradeNumber')
            self.logger.info(f"Trade {trade_number} identified and saved")
            print(f"Saved identified trade {trade_number} to matched_trades.json")
        except Exception as e:
            self.logger.error(f"Failed to save identified trade: {str(e)}")
            print(f"Error saving identified trade: {e}")

    def save_email_match(self, trade_data: dict, email_data: dict, status: str = None):
        """Save email match to email_matches.json"""
        email_matches_file = os.path.join(self.assets_path, 'email_matches.json')
        try:
            # Create file with empty list if it doesn't exist
            if not os.path.exists(email_matches_file):
                with open(email_matches_file, 'w', encoding='utf-8') as f:
                    f.write('[]')
            
            # Read existing matches
            with open(email_matches_file, 'r', encoding='utf-8') as f:
                matches = json.load(f)
            
            # Create new match record using only email data
            new_match = {
                "EmailSender": email_data.get("sender_email"),
                "EmailDate": email_data.get("received_date"),
                "EmailTime": email_data.get("received_time"),
                "EmailSubject": email_data.get("subject"),
                "InferredTradeID": int(trade_data.get("TradeNumber", 0)),
                "CounterpartyID": trade_data.get("CounterpartyID"),
                "CounterpartyName": trade_data.get("CounterpartyName"),
                "ProductType": trade_data.get("ProductType"),
                "Trader": None,
                "Currency1": trade_data.get("Currency1"),
                "QuantityCurrency1": float(trade_data.get("QuantityCurrency1", 0)),
                "Currency2": trade_data.get("Currency2"),
                "QuantityCurrency2": float(trade_data.get("QuantityCurrency2", 0)) if trade_data.get("QuantityCurrency2") else 0,
                "Buyer": trade_data.get("Buyer"),
                "Seller": trade_data.get("Seller"),
                "SettlementType": trade_data.get("SettlementType"),
                "SettlementCurrency": trade_data.get("SettlementCurrency"),
                "ValueDate": trade_data.get("ValueDate"),
                "MaturityDate": trade_data.get("MaturityDate"),
                "PaymentDate": trade_data.get("PaymentDate"),
                "Duration": int(trade_data.get("Duration", 0)),
                "ForwardPrice": float(trade_data.get("ForwardPrice", 0)),
                "FixingReference": trade_data.get("FixingReference"),
                "CounterpartyPaymentMethod": trade_data.get("CounterpartyPaymentMethod"),
                "BankPaymentMethod": trade_data.get("BankPaymentMethod"),
                "EmailBody": email_data.get("body_content"),
                "status": status  # Add the status field
            }
            
            # Append new match
            matches.append(new_match)
            
            # Write back to file
            with open(email_matches_file, 'w', encoding='utf-8') as f:
                json.dump(matches, f, indent=2, ensure_ascii=False)
            
            trade_number = trade_data.get("TradeNumber")
            self.logger.info(f"Trade {trade_number} matched with email from {new_match['EmailSender']}")
            
            print(f"Saved email match from {new_match['EmailSender']} to email_matches.json with status: {status}")
        except Exception as e:
            self.logger.error(f"Failed to save email match: {str(e)}")
            print(f"Error saving email match: {e}")

    def is_valid_value(self, value):
        """Check if a value should be considered valid for merging"""
        if value is None:
            return False
        if isinstance(value, str) and value.strip() == "":
            return False
        if isinstance(value, (int, float)) and value == 0:
            return False
        return True

    async def handle_new_unread_email(self, new_emails):
        """Process new unread emails"""
        email_entities = self.load_email_entities('email_entities.json')
        
        # Choose your preferred AI provider
        AI_PROVIDER = "Anthropic"
        
        self.logger.info(f"Processing {len(new_emails)} new unread emails")
        
        for email in new_emails:
            print("\n" + "="*80)
            
            try:
                # Get basic email details with error checking
                raw_email = email.sender.email_address.address
                
                # Clean up the email address (remove the sandbox part)
                if '@sandbox.mgsend.net' in raw_email:
                    parts = raw_email.split('=')
                    username = parts[0]
                    domain = parts[1].split('@')[0]
                    sender_email = f"{username}@{domain}"
                else:
                    sender_email = raw_email

                # Get other details
                subject = getattr(email, 'subject', 'No subject')
                received_date = email.received_date_time.date().isoformat() if hasattr(email, 'received_date_time') else 'No date'
                received_time = email.received_date_time.time().isoformat() if hasattr(email, 'received_date_time') else 'No time'
                
                # Log email receipt
                self.logger.info(f"Processing email from {sender_email}")
                
                # Print comprehensive email details
                print(f"EMAIL DETAILS:")
                print(f"Subject: {subject}")
                print(f"Date: {received_date}")
                print(f"Time: {received_time}")
                print(f"From: {sender_email}")
                
                # Check sender against entities list
                entity_name, entity_display_name, client_id = self.get_entity_info(sender_email, email_entities)
                
                if entity_name:
                    print(f"Entity: {entity_display_name} ({entity_name})")
                    print(f"Client ID: {client_id}")
                    self.logger.info(f"Email sender identified as {entity_display_name}")
                else:
                    print("Email not registered")
                    self.logger.warning(f"Unregistered email sender: {sender_email}")
                    
                # Use the core utility for cleaning HTML
                if hasattr(email, 'body') and email.body and hasattr(email.body, 'content'):
                    body_content = clean_html(email.body.content)
                else:
                    body_content = 'No body content'
                    
                print("\nBODY CONTENT:")
                print("-" * 40)
                print(body_content[:1000] + "..." if len(body_content) > 1000 else body_content)
                print("-" * 40)
                
                # Collect email data
                email_data = {
                    "subject": subject,
                    "received_date": received_date,
                    "received_time": received_time,
                    "sender_email": sender_email,
                    "entity_name": entity_name,
                    "client_id": client_id,
                    "body_content": body_content,
                    "attachments_text": "\n".join([
                        f"- {att.name} ({att.content_type}): {getattr(att, 'extracted_text', 'No text extracted')[:1000]}"
                        for att in email.attachments
                    ]) if hasattr(email, 'attachments') and email.attachments else "No attachments"
                }
                
                # Process with LLM
                try:
                    self.logger.info("Sending email to LLM for processing")
                    
                    llm_response = self.llm_service.process_email_data(email_data, ai_provider=AI_PROVIDER)
                    print(f"\nLLM RESPONSE:")
                    print("-" * 40)
                    print(llm_response)
                    print("-" * 40)
                    
                    # Check if the response indicates a confirmation email
                    llm_data = json.loads(llm_response)
                    is_confirmation = llm_data["Email"]["Confirmation"].lower() == "yes"
                    
                    if is_confirmation:
                        
                        self.logger.info(f"Email identified as trade confirmation")
                        print("This email is a confirmation email.")
                        
                        # Process each trade in the LLM response
                        if "Trades" in llm_data and llm_data["Trades"]:
                            
                            for trade in llm_data["Trades"]:
                                trade_number = trade.get("TradeNumber")
                                if trade_number:
                                    self.logger.info(f"Trade {trade_number} referenced in email")
                                    
                                    # Try to find the trade in unmatched_trades.json
                                    trade_details = self.email_processor.get_trade_details(trade_number)
                                    if trade_details:
                                        print(f"Trade {trade_number} found")
                                        
                                        self.logger.info(f"Trade {trade_number} found in entity system")
                                        
                                        # Always save as identified trade, which goes in the top-left grid
                                        self.save_identified_trade(trade_details)
                                        
                                        # Check if trade is confirmed
                                        if trade.get("Confirmation_OK", "").lower() == "yes":
                                            # If the trade is confirmed by the client, save the email match with the very same trade in the top-right grid
                                            print(f"Trade {trade_number} is confirmed - saving email match")
                                            self.save_email_match(trade_details, email_data, "Confirmation OK")
                                        else:
                                            # In this case the client has indicated that there is at least one data point that is not correct in the trade
                                            print(f"Trade {trade_number} found but not confirmed")
                                            self.logger.warning(f"Trade {trade_number} has discrepancies")
                                            
                                            # Create a merged trade data dictionary with the Murex trade details as our starting point
                                            merged_trade = trade_details.copy()
                                            
                                            # Track what fields were updated from the email
                                            updated_fields = {}
                                            
                                            # And then we can overwrite with any data that has valid values from the email or attachments
                                            for field, value in trade.items():
                                                if self.is_valid_value(value):
                                                    updated_fields[field] = {
                                                        "before": merged_trade.get(field),
                                                        "after": value
                                                    }
                                                    merged_trade[field] = value
                                                    print(f"Updating {field} to {value} from email")
                                                    
                                            # Log the updated fields
                                            if updated_fields:
                                                self.logger.warning(f"Updated trade {trade_number} with data from email")

                                            # Save the merged trade data
                                            self.save_email_match(merged_trade, email_data, "Difference")
                                    else:
                                        # Client email references a trade we don't have in our system
                                        print(f"Trade {trade_number} not found")
                                        self.logger.warning(f"Trade {trade_number} not found in entity system")
                                        
                                        # Create a minimal trade record for unrecognized trades
                                        unrecognized_trade = {
                                            "TradeNumber": trade_number,
                                            "CounterpartyID": trade.get("CounterpartyID", "Not available"),
                                            "CounterpartyName": trade.get("CounterpartyName", "Not available"),
                                            "ProductType": "Not a recognized trade",
                                            "Currency1": trade.get("Currency1", ""),
                                            "QuantityCurrency1": float(trade.get("QuantityCurrency1", 0)),
                                            "Currency2": trade.get("Currency2", ""),
                                            "QuantityCurrency2": float(trade.get("QuantityCurrency2", 0)),
                                            "Buyer": trade.get("Buyer", ""),
                                            "Seller": trade.get("Seller", ""),
                                            "SettlementType": trade.get("SettlementType", ""),
                                            "SettlementCurrency": trade.get("SettlementCurrency", ""),
                                            "ValueDate": trade.get("ValueDate", ""),
                                            "MaturityDate": trade.get("MaturityDate", ""),
                                            "PaymentDate": trade.get("PaymentDate", ""),
                                            "Duration": int(trade.get("Duration", 0)),
                                            "ForwardPrice": float(trade.get("ForwardPrice", 0)),
                                            "FixingReference": trade.get("FixingReference", ""),
                                            "CounterpartyPaymentMethod": trade.get("CounterpartyPaymentMethod", ""),
                                            "BankPaymentMethod": trade.get("BankPaymentMethod", "")
                                        }
                                        self.save_email_match(unrecognized_trade, email_data, "Unrecognized")
                        else:
                            print("No trades identified in the email")
                            self.logger.info("No trades identified in confirmation email")
                    else:
                        print("This email is NOT a confirmation email.")
                        self.logger.info("Email not relevant to trade confirmation")
                        await self.email_processor.move_email_to_folder(email, "Inbox/Confirmations/Not Relevant")
                    
                except Exception as e:
                    self.logger.error(f"Error processing email with LLM: {str(e)}")
                    print(f"Error processing with LLM: {str(e)}")
                    
            except Exception as e:
                self.logger.error(f"Error processing email: {str(e)}")
                print(f"Error processing email: {str(e)}")
                
            print("="*80 + "\n")