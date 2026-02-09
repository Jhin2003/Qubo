from typing import List
from pathlib import Path
import shutil
import os

# Removed "Depends" and "OAuth2PasswordBearer" from imports
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

# Removed jwt_auth import
# from app.utils.jwt_auth import verify_access_token 

# Consolidated imports
from app.services.file_service import process_file, delete_file_data 

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_STORE = BASE_DIR / "data_store"
UPLOAD_DIR = DATA_STORE / "pdfs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Removed oauth2_scheme definition

@router.get("/files")
async def list_files(): 
    files = []
    for file in UPLOAD_DIR.glob("*.pdf"):
        files.append({
            "filename": file.name,
            "url": f"http://localhost:8000/files/{file.name}", 
        })
    return {"files": files}

@router.get("/files/{filename}")
async def get_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

# Removed "current_user" argument and "Depends"
@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []
    
    allowed_extensions = {".pdf", ".docx", ".txt"}
    for file in files:
        try:
            filename = file.filename  
            
            file_extension = Path(filename).suffix.lower()
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=400,
                    detail=f"File type '{file_extension}' is not allowed. Please upload PDF, DOCX, or TXT."
                )
            
            file_path = UPLOAD_DIR / filename
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            num_chunks, output_path = process_file(str(file_path), filename)

            results.append({
                "filename": filename,
                "chunks_processed": num_chunks,
                "output_file": str(output_path),
                "message": "✅ Uploaded and processed successfully",
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "error": str(e),
                "message": "❌ Failed to upload or process",
            })

    return {"results": results}

# Removed "current_user" argument and "Depends"
@router.delete("/files/{filename}")
async def delete_file(filename: str):
    # 1. Security: Prevent path traversal
    upload_dir_resolved = UPLOAD_DIR.resolve()
    file_path = (UPLOAD_DIR / filename).resolve()
    
    if file_path.parent != upload_dir_resolved:
        raise HTTPException(status_code=400, detail="Invalid filename")

    # 2. Check existence
    if not file_path.exists():
         raise HTTPException(status_code=404, detail="File not found")

    try:
        # 3. Call the service to handle cleanup
        report = delete_file_data(filename, UPLOAD_DIR)
        
        return {
            "filename": filename, 
            "status": "deleted",
            "details": report
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")