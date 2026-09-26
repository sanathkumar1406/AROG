"""
AROG Routes - OCR endpoint.
Uses existing TrOCR ONNX model. Does NOT auto-save results.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from PIL import Image
import io

from app.schemas.ai import OCRResponse
from app.services.ocr_service import run_ocr
from app.database.models import User
from app.routes.auth import get_current_user

router = APIRouter(prefix="/api/ocr", tags=["OCR"])

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.post("", response_model=OCRResponse)
async def extract_text(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an image/document and extract text using TrOCR.
    
    The extracted text is returned for doctor review.
    It is NOT automatically saved to any patient record.
    The doctor must review/edit and explicitly confirm saving.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file contents
    try:
        contents = await file.read()
    except Exception:
        raise HTTPException(status_code=400, detail="Failed to read uploaded file.")

    # Validate file size
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024*1024)} MB.")

    # Validate it's a real image
    try:
        image = Image.open(io.BytesIO(contents))
        image.verify()
        # Re-open after verify (verify closes the image)
        image = Image.open(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid image file. Could not decode.")

    # Run OCR
    try:
        result = run_ocr(image)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return OCRResponse(
        extracted_text=result["extracted_text"],
        structured_data=result.get("structured_data"),
        confidence=result.get("confidence"),
        message="Text extracted successfully. Please review and edit before saving to patient record.",
    )

