from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from typing import List
from PyPDF2 import PdfMerger
import io

# FastAPI app banaya
app = FastAPI(
    title="ToolSonics Backend",
    version="1.0.0",
    description="PDF tools backend for ToolSonics"
)

# Test route - sirf check karne ke liye
@app.get("/")
def root():
    return {"message": "ToolSonics backend is running!"}


# ✅ MERGE PDF BACKEND API
@app.post("/pdf/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    """
    Ye API multiple PDF files ko ek PDF me merge karegi.
    """

    # Check: kam se kam 2 PDF honi chahiye
    if len(files) < 2:
        return JSONResponse(
            {"error": "Please upload at least 2 PDF files."},
            status_code=400
        )

    merger = PdfMerger()

    try:
        # Har file ko read karke merger me add kar rahe hain
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                return JSONResponse(
                    {"error": "All files must be PDF files."},
                    status_code=400
                )

            content = await f.read()           # file bytes
            pdf_stream = io.BytesIO(content)   # memory me PDF
            merger.append(pdf_stream)          # merger me add

        # Output merged PDF ko bhi memory me bana rahe hain
        output_stream = io.BytesIO()
        merger.write(output_stream)
        merger.close()
        output_stream.seek(0)

        # Client ko merged.pdf download ke liye bhej rahe hain
        return StreamingResponse(
            output_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
