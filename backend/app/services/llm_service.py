import os
import anthropic
import json
from datetime import datetime
from typing import Dict, Optional
import google.generativeai as gemini
from openai import OpenAI
from .email_processor_service import EmailProcessorService
from ..config import Config
from ..core.logger import logger
from core_logging.client import EventType, LogLevel
from core_ai_cost import AICostCalculator, AIProvider

class LLMService:
    def __init__(self, graph_client=None):
        self.openai_api_key = Config.OPENAI_API_KEY
        self.anthropic_api_key = Config.ANTHROPIC_API_KEY
        gemini.configure(api_key=Config.GOOGLE_API_KEY)

        # Get parameters from environment variables
        self.my_entity = os.environ.get('MY_ENTITY')

        logger.info(
            "Initializing LLM Service",
            event_type=EventType.SYSTEM_EVENT,
            entity=self.my_entity,
            user_id="system",
            data={
                "openai_available": bool(self.openai_api_key),
                "anthropic_available": bool(self.anthropic_api_key),
                "gemini_available": bool(Config.GOOGLE_API_KEY)
            },
            tags=["initialization", "service", "llm"]
        )

        if self.openai_api_key:
            self.openai_client = OpenAI(api_key=self.openai_api_key)
            logger.info(
                "OpenAI client initialized",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["llm", "openai", "initialization"]
            )
        else:
            logger.warning(
                "OpenAI API key not set - OpenAI features unavailable",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["llm", "openai", "warning"]
            )
            
        if self.anthropic_api_key:
            self.anthropic_client = anthropic.Client(api_key=self.anthropic_api_key)
            logger.info(
                "Anthropic client initialized",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["llm", "anthropic", "initialization"]
            )
        else:
            logger.warning(
                "Anthropic API key not set - Claude features unavailable",
                event_type=EventType.SYSTEM_EVENT,
                entity=self.my_entity,
                user_id="system",
                tags=["llm", "anthropic", "warning"]
            )

        self.email_processor = EmailProcessorService(graph_client=graph_client)

        self.cost_calculator = AICostCalculator(
            app_name="Confirmation Manager",
            log_client=logger
        )

    
    def process_email_data(self, email_data: Dict, ai_provider: str = "OpenAI") -> str:
        """Process email data using the specified AI provider."""
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
        
        # Format the email data into a clear text format
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
            if ai_provider == "OpenAI":
                if not self.openai_api_key:
                    error_msg = "OpenAI API key is not set"
                    logger.error(
                        error_msg,
                        event_type=EventType.INTEGRATION,
                        entity=self.my_entity,
                        user_id="system",
                        tags=["llm", "openai", "error", "configuration"]
                    )
                    raise ValueError(error_msg)

                model = "gpt-4-turbo-preview"

                logger.info(
                    "Sending request to OpenAI API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"model": model},
                    tags=["llm", "openai", "request"]
                )
                
                # Calculate execution time
                start_time = datetime.utcnow()
                request_id = f"req-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                response = self.openai_client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    max_tokens=1000,
                    temperature=0
                )
                
                # Calculate execution time
                end_time = datetime.utcnow()
                execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

                # Calculate token counts
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens
                
                # Calculate cost
                cost_data = self.cost_calculator.calculate_cost(
                    provider=AIProvider.OPENAI,
                    model_name=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    log_cost=True,
                    user_id="system",
                    entity=self.my_entity,
                    context={
                        "request_id": request_id,
                        "duration_ms": str(execution_time_ms),
                        "text_length": str(len(prompt)),
                        "ai_provider": "OpenAI",
                        "model": model
                    },
                    tags=["ai-cost", "openai", "gpt4", "extraction"]
                )


                logger.info(
                    "Received response from OpenAI API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"completion_tokens": len(response.choices[0].message.content)},
                    tags=["llm", "openai", "response"]
                )
                
                return response.choices[0].message.content

            elif ai_provider == "Anthropic":
                if not self.anthropic_api_key:
                    error_msg = "Anthropic API key is not set"
                    logger.error(
                        error_msg,
                        event_type=EventType.INTEGRATION,
                        entity=self.my_entity,
                        user_id="system",
                        tags=["llm", "anthropic", "error", "configuration"]
                    )
                    raise ValueError(error_msg)
                
                logger.info(
                    "Sending request to Anthropic API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"model": "claude-3-5-sonnet-20241022"},
                    tags=["llm", "anthropic", "request"]
                )
                
                # Calculate execution time
                start_time = datetime.utcnow()
                request_id = f"req-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                model = "claude-3-5-sonnet-20241022"

                response = self.anthropic_client.messages.create(
                    model=model,
                    messages=[{
                        "role": "user",
                        "content": prompt
                    }],
                    max_tokens=1000,
                    temperature=0
                )
                
                # Calculate execution time
                end_time = datetime.utcnow()
                execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

                # Calculate token counts
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                
                # Calculate cost
                cost_data = self.cost_calculator.calculate_cost(
                    provider=AIProvider.ANTHROPIC,
                    model_name=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    log_cost=True,
                    user_id="system",
                    entity=self.my_entity,
                    context={
                        "request_id": request_id,
                        "duration_ms": str(execution_time_ms),
                        "text_length": str(len(prompt)),
                        "ai_provider": "Anthropic",
                        "model": model
                    },
                    tags=["ai-cost", "anthropic", "claude35", "extraction"]
                )

                logger.info(
                    "Received response from Anthropic API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"response_length": len(response.content[0].text)},
                    tags=["llm", "anthropic", "response"]
                )
                
                return response.content[0].text
            
            elif ai_provider == "Google":
                if not Config.GOOGLE_API_KEY:
                    error_msg = "Google API key is not set"
                    logger.error(
                        error_msg,
                        event_type=EventType.INTEGRATION,
                        entity=self.my_entity,
                        user_id="system",
                        tags=["llm", "google", "error", "configuration"]
                    )
                    raise ValueError(error_msg)
                
                model = "gemini-2.0-pro-exp-02-05"

                logger.info(
                    "Sending request to Google Gemini API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"model": model},
                    tags=["llm", "google", "request"]
                )
                
                # Calculate execution time
                start_time = datetime.utcnow()
                request_id = f"req-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

                model = gemini.GenerativeModel(
                    model_name=model,
                    generation_config={
                        "temperature": 0,
                        "top_p": 1,
                        "top_k": 1,
                        "max_output_tokens": 1000,
                    }
                )
                
                response = model.generate_content(prompt)
                
                # Calculate execution time
                end_time = datetime.utcnow()
                execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

                # Calculate token counts
                # For Google Gemini, token counts are not directly available in the response
                # We'll need to estimate them based on text length
                prompt_text_length = len(prompt)
                response_text_length = len(response.text)
                
                # Rough estimation: ~4 characters per token for English text
                estimated_input_tokens = int(prompt_text_length / 4)
                estimated_output_tokens = int(response_text_length / 4)

                # Calculate cost
                cost_data = self.cost_calculator.calculate_cost(
                    provider=AIProvider.GOOGLE,
                    model_name=model,
                    input_tokens=estimated_input_tokens,
                    output_tokens=estimated_output_tokens,
                    log_cost=True,
                    user_id="system",
                    entity=self.my_entity,
                    context={
                        "request_id": request_id,
                        "duration_ms": str(execution_time_ms),
                        "text_length": str(len(prompt)),
                        "ai_provider": "Google",
                        "model": model
                    },
                    tags=["ai-cost", "google", "gemini20", "extraction"]
                )

                logger.info(
                    "Received response from Google Gemini API",
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"response_length": len(response.text)},
                    tags=["llm", "google", "response"]
                )
                
                return response.text

            else:
                error_msg = f"Invalid AI provider specified: {ai_provider}. Use 'OpenAI', 'Anthropic', or 'Google'"
                logger.error(
                    error_msg,
                    event_type=EventType.INTEGRATION,
                    entity=self.my_entity,
                    user_id="system",
                    data={"provider": ai_provider},
                    tags=["llm", "error", "configuration"]
                )
                raise ValueError(error_msg)

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
            result = await self.email_processor.process_email_result(email_obj, llm_response)
            
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