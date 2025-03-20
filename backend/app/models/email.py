class Email:
    """Model representing an email entity"""
    def __init__(self, 
                 message_id=None, 
                 subject=None,
                 sender_email=None,
                 sender_name=None,
                 received_date=None,
                 received_time=None,
                 body_content=None,
                 attachments=None,
                 entity_name=None,
                 client_id=None):
        self.message_id = message_id
        self.subject = subject
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.received_date = received_date
        self.received_time = received_time
        self.body_content = body_content
        self.attachments = attachments or []
        self.entity_name = entity_name
        self.client_id = client_id
        
    def to_dict(self):
        return {
            "subject": self.subject,
            "received_date": self.received_date,
            "received_time": self.received_time,
            "sender_email": self.sender_email,
            "entity_name": self.entity_name,
            "client_id": self.client_id,
            "body_content": self.body_content,
            "attachments_text": "\n".join([
                f"- {att.get('name')} ({att.get('type')}): {att.get('content', 'No text extracted')[:1000]}"
                for att in self.attachments
            ]) if self.attachments else "No attachments"
        }