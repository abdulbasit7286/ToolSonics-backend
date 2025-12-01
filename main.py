from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io

# Create FastAPI app
app = FastAPI(
    title="ToolSonics Backend",
    version="1.0.0",
    description="PDF tools backend for ToolSonics"
)

# 🔥 CORS FIX — allow frontend (GitHub Pages) to call backend (Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # all domains allowed (later tu yaha apna domain bhi laga sakta hai)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# ✅ SPLIT PDF API (NEW)
@app.post("/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...)
):
    """
    Ek single PDF ka selected page range (start_page to end_page) nikal ke naya PDF banata hai.
    Page numbering 1-based hai (1 = first page).
    """

    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": "Please upload a PDF file."},
            status_code=400
        )

    try:
        # File read karo
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        total_pages = len(reader.pages)

        # Validate page range (1-based)
        if start_page < 1 or end_page < 1 or start_page > end_page:
            return JSONResponse(
                {"error": "Invalid page range."},
                status_code=400
            )

        if end_page > total_pages:
            return JSONResponse(
                {"error": f"PDF has only {total_pages} pages."},
                status_code=400
            )

        # Required pages add karo
        # user ne jo page number diya hai wo 1-based hai, Reader 0-based
        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])

        # Output memory me
        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        return StreamingResponse(
            output_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=split.pdf"}
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to split PDF: {str(e)}"},
            status_code=500
        )
