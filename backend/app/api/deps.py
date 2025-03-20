# backend/app/api/deps.py
from ..services.email_processor_service import EmailProcessorService
from ..services.llm_service import LLMService
from ..services.confirmation_service import ConfirmationService
from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from ..config import Config
import logging

def get_graph_client():
    """Get Microsoft Graph client"""
    try:
        credentials = ClientSecretCredential(
            tenant_id=Config.GRAPH_TENANT_ID,
            client_id=Config.GRAPH_CLIENT_ID,
            client_secret=Config.GRAPH_CLIENT_SECRET
        )
        return GraphServiceClient(credentials=credentials)
    except Exception as e:
        logging.error(f"Failed to initialize Graph client: {str(e)}")
        return None

def get_email_processor_service():
    """Get email processor service instance"""
    graph_client = get_graph_client()
    return EmailProcessorService(graph_client=graph_client)

def get_llm_service():
    """Get LLM service instance"""
    graph_client = get_graph_client()
    return LLMService(graph_client=graph_client)

def get_confirmation_service():
    """Get confirmation service instance"""
    graph_client = get_graph_client()
    llm_service = get_llm_service()
    email_processor = get_email_processor_service()
    return ConfirmationService(
        graph_client=graph_client,
        llm_service=llm_service,
        email_processor_service=email_processor
    )