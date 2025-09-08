from fastapi import APIRouter, UploadFile, File
from typing import List
from pathlib import Path
import shutil
from app.services.file_service import process_pdf_chunks

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_STORE = BASE_DIR / "data_store"
UPLOAD_DIR = DATA_STORE / "pdfs"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/files")
async def list_files():
    files = []
    for file in UPLOAD_DIR.glob("*.pdf"):
        files.append({
            "filename": file.name,
            "path": str(file),
        })
    return {"files": files}


@router.post("/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    results = []

    for file in files:
        try:
            # Save the PDF into UPLOAD_DIR
            file_path = UPLOAD_DIR / file.filename
            with open(file_path, "wb") as f:
                shutil.copyfileobj(file.file, f)

            # Process with service
            num_chunks, output_path = process_pdf_chunks(str(file_path), file.filename)

            results.append({
                "filename": file.filename,
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

