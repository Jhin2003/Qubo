import os
import shutil
import tempfile
from typing import List
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.file_service import process_file, delete_file_data 

router = APIRouter()

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []
    allowed_extensions = {".pdf", ".docx"} 
    
    for file in files:
        try:
            filename = file.filename  
            file_extension = os.path.splitext(filename)[1].lower()
            
            if file_extension not in allowed_extensions:
                results.append({
                    "filename": filename,
                    "status": "error",
                    "message": f"❌ File type '{file_extension}' not allowed."
                })
                continue
            
            # 1. Save to system temp file
            temp_dir = tempfile.gettempdir()
            temp_file_path = os.path.join(temp_dir, filename)
            
            with open(temp_file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 2. Process with content_type passed through
            num_chunks = process_file(temp_file_path, filename, file.content_type)

            if num_chunks == 0:
                results.append({
                    "filename": filename,
                    "status": "rejected",
                    "message": "❌ File rejected (semantic threshold not met)",
                })
            else:
                results.append({
                    "filename": filename,
                    "chunks_processed": num_chunks,
                    "status": "success",
                    "message": "✅ Uploaded and processed successfully",
                })
                
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
                "status": "error",
                "message": "❌ Processing failed",
            })

    return {"results": results}

@router.delete("/files/{filename}")
async def delete_file(filename: str):
    try:
        report = delete_file_data(filename)
        return {"filename": filename, "status": "deleted", "details": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")