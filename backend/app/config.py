import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-for-confirmation-manager'
    GRAPH_CLIENT_ID = os.environ.get('AZURE_CLIENT_ID')
    GRAPH_CLIENT_SECRET = os.environ.get('AZURE_CLIENT_SECRET')
    GRAPH_TENANT_ID = os.environ.get('AZURE_TENANT_ID')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    USER_EMAIL = os.environ.get('USER_EMAIL', 'ben.clark@palace.cl')
    ASSETS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../frontend/public/assets'))