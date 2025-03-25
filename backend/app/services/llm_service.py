import os
import json
from datetime import datetime
from typing import Dict, Optional
import asyncio
from ..config import Config
from ..core.logger import logger
from core_logging.client import EventType, LogLevel
from core_ai_cost import AICostCalculator, AIProvider
from llm_services import LLMService as CoreLLMService, LLMRequest, LLMResponse

class LLMService:
    def __init__(self, graph_client=None):
        self.graph_client = graph_client
        self.my_entity = os.environ.get('MY_ENTITY')

        # Record available API keys
        self.services_available = {
            "OpenAI": bool(Config.OPENAI_API_KEY),
            "Anthropic": bool(Config.ANTHROPIC_API_KEY),
            "Google": bool(Config.GOOGLE_API_KEY)
        }

        logger.info(
            "Initializing LLM Service",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            data=self.services_available,
            tags=["initialization", "service", "llm"]
        )

        # Initialize cost calculator
        self.cost_calculator = AICostCalculator(
            app_name="Confirmation Manager",
            log_client=logger
        )

        # Cache for LLM service instances
        self.llm_instances = {}

    def _get_llm_instance(self, provider: str):
        """Get or create a provider-specific LLM service instance"""
        if provider not in self.llm_instances:
            api_key = None
            if provider == "OpenAI":
                api_key = Config.OPENAI_API_KEY
            elif provider == "Anthropic":
                api_key = Config.ANTHROPIC_API_KEY
            elif provider == "Google":
                api_key = Config.GOOGLE_API_KEY
            
            if not api_key:
                error_msg = f"{provider} API key is not set"
                logger.error(
                    error_msg,
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    tags=["llm", provider.lower(), "error", "configuration"]
                )
                raise ValueError(error_msg)
                
            # Initialize provider-specific service
            self.llm_instances[provider] = CoreLLMService.get_instance(provider, api_key)
            
            logger.info(
                f"{provider} client initialized",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["llm", provider.lower(), "initialization"]
            )
            
        return self.llm_instances[provider]
    
    def process_email_data(self, email_data: Dict, ai_provider: str = "OpenAI") -> str:
        """Process email data using the specified AI provider (synchronous wrapper)"""
        # Use ThreadPoolExecutor to run async code from sync context
        import concurrent.futures
        import threading
        
        # Define function to run in separate thread
        def run_async_in_thread():
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                # Run async function to completion
                return loop.run_until_complete(
                    self._async_process_email_data(email_data, ai_provider)
                )
            finally:
                loop.close()
        
        # Execute in thread pool to avoid event loop conflicts
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_async_in_thread)
            return future.result()
            
    async def _async_process_email_data(self, email_data: Dict, ai_provider: str = "OpenAI") -> str:
        """Async implementation of email data processing"""
        logger.info(
            f"Processing email with {ai_provider}",
            event_type=EventType.INTEGRATION,
            entity=self.my_entity,
            user_id="system",
            data={
                "provider": ai_provider, 
                "subject": email_data.get('subject'),
                "sender": email_data.get('sender_email')
            },
            tags=["llm", "processing", ai_provider.lower()]
        )
        
        # Format the email data
        formatted_data = f"""
        Email Details:
        Subject: {email_data.get('subject')}
        Date: {email_data.get('received_date')}
        Time: {email_data.get('received_time')}
        From: {email_data.get('sender_email')}
        Entity: {email_data.get('entity_name')}
        Client ID: {email_data.get('client_id')}

        Body Content:
        {email_data.get('body_content')}

        Attachments:
        {email_data.get('attachments_text', 'No attachments')}
        """

        prompt = f"""Tell me if this email is regarding a confirmation of a trade, regardless of whether the sender is confirming or rejecting it:

                {formatted_data}

                Look for the trade number in the subject of the email, in the body and in the attachment text.

                I also need you to extract some data from the email body and the attachments. You should use the email as a more likely source of truth.
                Data in the email body should override data in the attachments. This is because it is text from a human indicating whether they agree with the
                trade data in the attachments or not. Data in the email body should also override data in the email subject, as it is possible that the conversation
                has moved on from the initial subject line.

                The specific data you need to find is as follows:
                 
                - Trade Number, a number indicating the ID of the trade
                - Counterparty ID, a number indicating the ID of the counterparty {email_data.get('client_id')}
                - Counterparty Name, a company name {email_data.get('entity_name')}
                - Product Type, usually one of the following values: "Seguro de Cambio", "Seguro de Inflación", "Arbitraje", "Forward" or "Spot"
                - Currency 1, an ISO 4217 currency code
                - Amount of Currency 1, a number
                - Currency 2, an ISO 4217 currency code
                - Amount of Currency, a number (the amount of currency 1 multiplied by the forward price)
                - Buyer, a company name
                - Seller, a company name
                - Settlement Type, usually one of the following values: "Non-Deliverable", "Deliverable"
                - Settlement Currency, an ISO 4217 currency code
                - Value Date, a date, which can be in different formats
                - Maturity Date, a date, which can be in different formats
                - Payment Date, a date, which can be in different formats
                - Duration, an integer number, indicating the number of days between the value date and the maturity date
                - Forward Price, a number usually with decimal places
                - Fixing Reference, usually one of the following values: "USD Obs", "CLP Obs"
                - Counterparty Payment Method, look in fields labelled "Forma de Pago". Usually one of the following values: "Trans Alto Valor", "ComBanc", "SWIFT", "Cuenta Corriente".
                - Bank Payment Method, look in fields labelled "Forma de Pago". Usually one of the following values: "Trans Alto Valor", "ComBanc", "SWIFT", "Cuenta Corriente"

                Return this in a JSON format, but do not include any markdown formatting such as ```json or ```. This causes errors so I really need you to return it without any markdown formatting.
                DO NOT return any other text than the JSON, as this causes errors.

                The required structured of the JSON file is as follows:

                {{
                    "Email": {{
                        "Email_subject": string,
                        "Email_sender": string,
                        "Email_date": date (dd-mm-yyyy),
                        "Email_time": time (hh:mm:ss),
                        "Confirmation": string (Yes if it has at least one confirmation of a trade (regardless of whether the counterparty agrees or disagrees), or No if there are no references to confirmations of trades)
                        "Num_trades": integer (the number of trades referred to in the email),
                    }},
                    "Trades": [
                        {{
                            "Confirmation_OK": string (Yes or No),
                            "TradeNumber": string,
                            "CounterpartyID": string,
                            "CounterpartyName": string,
                            "ProductType": string,
                            "Currency1": string (ISO 4217 currency code),
                            "QuantityCurrency1": number to a minimum of two decimal places,
                            "Currency2": string (ISO 4217 currency code),
                            "QuantityCurrency2": number to a minimum of two decimal places,
                            "Buyer": string,
                            "Seller": string,
                            "SettlementType": string, ("Non-Deliverable" or "Deliverable"),
                            "SettlementCurrency": string (ISO 4217 currency code),
                            "ValueDate": date in format dd-mm-yyyy,
                            "MaturityDate": date in format dd-mm-yyyy,
                            "PaymentDate": date in format dd-mm-yyyy,
                            "Duration": integer,
                            "ForwardPrice": number to a minimum of two decimal places,
                            "FixingReference": string,
                            "CounterpartyPaymentMethod": string,
                            "BankPaymentMethod": string
                        }}
                        // Repeat as many times as there are trades in the email
                    ]
                }}

                Now STOP for a minute, before you return the JSON. I need you to compare the data you have extracted into the Trades array in the JSON with the data in the email. If there is any difference on a specific field, overwrite the data in the JSON with the data you think is correct in the email.
                Remember that QuantityCurrency2 is the amount of currency 1 multiplied by the forward price, so if any of these values have changed, you need to update QuantityCurrency2.

                I repeat, the email body is the best source of truth.

                DO NOT return any other text than the JSON, as this causes errors. NO MARKDOWN.
            """

        try:
            # Get the appropriate LLM service for the provider
            llm_service = self._get_llm_instance(ai_provider)
            
            # Select the right model based on the provider
            model = self._get_default_model(ai_provider)
            
            logger.info(
                f"Sending request to {ai_provider} API",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={"model": model},
                tags=["llm", ai_provider.lower(), "request"]
            )
            
            # Calculate execution time
            start_time = datetime.utcnow()
            request_id = f"req-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
            system_message = "You are an expert in the field of OTC derivatives and FX. You have many years of experience in trade confirmations so you are able to extract the relevantdata from the email and return it in a structured format."
            
            # Create the request object
            request = LLMRequest(
                prompt=prompt,
                system_message=system_message,
                model=model,
                max_tokens=1000,
                temperature=0
            )
            
            # Send the request to the LLM service
            response = await llm_service.generate(request)
            
            # Calculate execution time
            end_time = datetime.utcnow()
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Log metrics based on provider
            ai_provider_enum = self._get_provider_enum(ai_provider)
            
            # Calculate cost
            cost_data = self.cost_calculator.calculate_cost(
                provider=ai_provider_enum,
                model_name=model,
                input_tokens=response.metadata.get("input_tokens", response.tokens_used // 2),
                output_tokens=response.metadata.get("output_tokens", response.tokens_used // 2),
                log_cost=True,
                user_id="system",
                entity=self.my_entity,
                context={
                    "request_id": request_id,
                    "duration_ms": str(execution_time_ms),
                    "text_length": str(len(prompt)),
                    "ai_provider": ai_provider,
                    "model": model
                },
                tags=["ai-cost", ai_provider.lower(), self._get_model_tag(model), "extraction"]
            )
            
            logger.info(
                f"Received response from {ai_provider} API",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={"response_length": len(response.content)},
                tags=["llm", ai_provider.lower(), "response"]
            )
            
            return response.content

        except Exception as e:
            logger.log_exception(
                e,
                message=f"Error processing with {ai_provider} API",
                entity=self.my_entity,
                user_id="system",
                data={
                    "provider": ai_provider, 
                    "subject": email_data.get('subject'),
                    "error": str(e)
                },
                level=LogLevel.ERROR,
                tags=["llm", "error", ai_provider.lower()]
            )
            raise Exception(f"Error processing with {ai_provider} API: {str(e)}")
    
    def _get_default_model(self, provider: str) -> str:
        """Get the default model name for a provider"""
        if provider == "OpenAI":
            return "gpt-4-turbo"
        elif provider == "Anthropic":
            return "claude-3-5-sonnet-20241022"
        elif provider == "Google":
            return "gemini-2.0-pro-exp-02-05"
        else:
            return "unknown-model"
    
    def _get_provider_enum(self, provider: str) -> AIProvider:
        """Convert provider string to AIProvider enum"""
        if provider == "OpenAI":
            return AIProvider.OPENAI
        elif provider == "Anthropic":
            return AIProvider.ANTHROPIC
        elif provider == "Google":
            return AIProvider.GOOGLE
        else:
            return AIProvider.OTHER
    
    def _get_model_tag(self, model: str) -> str:
        """Get a simplified tag for the model"""
        if "gpt-4" in model:
            return "gpt4"
        elif "claude-3-5" in model:
            return "claude35"
        elif "gemini" in model:
            return "gemini20"
        else:
            return "other"

    async def process_email(self, email_content, email_obj, ai_provider="Google"):
        """Process an email and determine if it's a confirmation"""
        try:
            logger.info(
                f"Processing email with {ai_provider}",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={
                    "provider": ai_provider,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None
                },
                tags=["email", "processing", "start"]
            )
            
            # Process with the specified AI provider
            llm_response = self.process_email_data(email_content, ai_provider=ai_provider)
            
            logger.info(
                "LLM response received, processing with email processor",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={"response_length": len(llm_response)},
                tags=["llm", "response", "processing"]
            )

            # Process the result using EmailProcessor
            from .email_processor_service import EmailProcessorService
            email_processor = EmailProcessorService(graph_client=self.graph_client)
            result = await email_processor.process_email_result(email_obj, llm_response)
            
            logger.info(
                "Email processing completed",
                event_type=EventType.INTEGRATION,
                entity=self.my_entity,
                user_id="system",
                data={
                    "is_confirmation": result.get("is_confirmation", False),
                    "trades_identified": len(result.get("identified_trade_details", []))
                },
                tags=["email", "processing", "complete"]
            )
            
            return result
            
        except Exception as e:
            logger.log_exception(
                e,
                message="Error processing email",
                entity=self.my_entity,
                user_id="system",
                data={
                    "provider": ai_provider,
                    "subject": email_obj.subject if hasattr(email_obj, 'subject') else None
                },
                tags=["email", "processing", "error"]
            )
            return {
                "is_confirmation": False,
                "trade_details": None,
                "error": str(e)
            }