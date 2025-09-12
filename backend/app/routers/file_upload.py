from typing import List
from pathlib import Path
import shutil
import os

from fastapi import APIRouter, UploadFile, File, HTTPException,Depends
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer
from app.utils.jwt_auth import verify_access_token

from app.services.file_service import process_pdf_chunks

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_STORE = BASE_DIR / "data_store"
UPLOAD_DIR = DATA_STORE / "pdfs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = verify_access_token(token)
        print(f"Received token: {token}")  # Debug print
        return payload  # You can return the user data or any other info from the token
    except HTTPException as e:
        raise e

# List all files with a secured token
@router.get("/files")
async def list_files(current_user: dict = Depends(get_current_user)):  # Depend on get_current_user
    files = []
    for file in UPLOAD_DIR.glob("*.pdf"):
        files.append({
            "filename": file.name,
            "url": f"http://localhost:8000/files/{file.name}",  # Adjust URL based on your server URL
        })
    return {"files": files}


@router.get("/files/{filename}")
async def get_file(filename: str):
    file_path = UPLOAD_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    else:
        raise HTTPException(status_code=404, detail="File not found")

@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...), current_user: dict = Depends(get_current_user)):
    results = []

    for file in files:
        try:
            filename = file.filename  # Securely handle the filename if necessary

            # Ensure file is a PDF
            if not filename.endswith('.pdf'):
                raise HTTPException(status_code=400, detail="Only PDF files are allowed")

            # Save the uploaded file to the server
            file_path = UPLOAD_DIR / filename
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            # Process the PDF file with your service (chunks processing, etc.)
            num_chunks, output_path = process_pdf_chunks(str(file_path), filename)

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
