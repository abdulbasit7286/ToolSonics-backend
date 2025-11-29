from fastapi import FastAPI, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfMerger
import io

# Create FastAPI app
app = FastAPI(
    title="ToolSonics Backend",
    version="1.0.0",
    description="PDF tools backend for ToolSonics"
)

# 🔥 CORS FIX — IMPORTANT
# Allow frontend (GitHub Pages) to access backend (Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # all domains allowed
    allow_credentials=True,
    allow_methods=["*"],      # all HTTP methods allowed
    allow_headers=["*"],      # all headers allowed
)

# Test route to check server is running
@app.get("/")
def root():
    return {"message": "ToolSonics backend is running with CORS enabled!"}


# ✅ MERGE PDF API
@app.post("/pdf/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    """
    Multiple PDF files ko merge karke ek hi PDF banata hai.
    """

    # At least 2 PDFs needed
    if len(files) < 2:
        return JSONResponse(
            {"error": "Please upload at least 2 PDF files."},
            status_code=400
        )

    merger = PdfMerger()

    try:
        # Har file merge karna
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                return JSONResponse(
                    {"error": "All files must be PDF files."},
                    status_code=400
                )

            content = await f.read()             # file bytes
            pdf_stream = io.BytesIO(content)     # memory stream
            merger.append(pdf_stream)            # merge

        # Final merged PDF output
        output_stream = io.BytesIO()
        merger.write(output_stream)
        merger.close()
        output_stream.seek(0)

        # User ko merged.pdf download karwane ke liye response
        return StreamingResponse(
            output_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to merge PDFs: {str(e)}"},
            status_code=500
        )
