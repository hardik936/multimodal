from fastapi import APIRouter, UploadFile, File, HTTPException, status
import shutil
import os
import uuid
from app.config import settings

router = APIRouter()

@router.post("", status_code=status.HTTP_201_CREATED)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to the server.
    Returns the file path.
    """
    # Create upload directory if it doesn't exist (should be done in config, but safe to check)
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    
    # Generate unique filename to prevent collisions
    # Keep original extension
    ext = os.path.splitext(file.filename)[1]
    filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        return {
            "filename": file.filename,
            "saved_filename": filename,
            "file_path": file_path,
            "content_type": file.content_type
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save file: {str(e)}"
        )
