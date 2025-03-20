from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class EmailUpdateSchema(BaseModel):
    emailId: int
    status: str

class UndoEmailStatusSchema(BaseModel):
    emailId: int

class ClearJsonFileSchema(BaseModel):
    fileType: str