# backend/app/api/endpoints/emails.py
from flask import request, jsonify, Blueprint

emails = Blueprint('emails', __name__)

from ..deps import get_email_processor_service

@emails.route('/update-email-status', methods=['POST'])
def update_email_status():
    data = request.json
    email_id = data.get('emailId')
    status = data.get('status')
    
    email_service = get_email_processor_service()
    result = email_service.update_email_status(email_id, status)
    
    return jsonify(result)

@emails.route('/undo-status-change', methods=['POST'])
def undo_status_change():
    data = request.json
    email_id = data.get('emailId')
    
    email_service = get_email_processor_service()
    result = email_service.undo_status_change(email_id)
    
    return jsonify(result)

@emails.route('/clear-json-file', methods=['POST'])
def clear_json_file():
    data = request.json
    file_type = data.get('fileType')
    
    if not file_type:
        return jsonify({"success": False, "message": "File type is required"})
    
    email_service = get_email_processor_service()
    result = email_service.clear_json_file(file_type)
    
    return jsonify(result)