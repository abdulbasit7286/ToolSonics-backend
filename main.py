from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io

app = FastAPI(
    title="ToolSonics Backend",
    version="1.1.0",
    description="PDF tools backend for ToolSonics"
)

# CORS so GitHub frontend can call Render backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # later tu apna domain specific bhi rakh sakta hai
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "ToolSonics backend is running with PDF tools!"}


# ✅ MERGE PDF
@app.post("/pdf/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        return JSONResponse(
            {"error": "Please upload at least 2 PDF files."},
            status_code=400
        )

    merger = PdfMerger()
    try:
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
                return JSONResponse(
                    {"error": "All files must be PDF files."},
                    status_code=400
                )
            content = await f.read()
            merger.append(io.BytesIO(content))

        output_stream = io.BytesIO()
        merger.write(output_stream)
        merger.close()
        output_stream.seek(0)

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


# ✅ SPLIT PDF (page range)
@app.post("/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...)
):
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": "Please upload a PDF file."},
            status_code=400
        )

    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        total_pages = len(reader.pages)

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

        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])

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


# 🔧 Helper: parse pages string like "2,4,7-9"
def parse_pages_to_delete(pages_str: str, total_pages: int):
    pages_to_delete = set()

    for part in pages_str.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start_s, end_s = part.split("-")
                start = int(start_s)
                end = int(end_s)
                if start > end:
                    start, end = end, start
                for p in range(start, end + 1):
                    if 1 <= p <= total_pages:
                        pages_to_delete.add(p)
            except ValueError:
                continue
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages_to_delete.add(p)
            except ValueError:
                continue

    return pages_to_delete


# ✅ DELETE PAGES FROM PDF
@app.post("/pdf/delete-pages")
async def delete_pages_pdf(
    file: UploadFile = File(...),
    pages: str = Form(...)
):
    """
    'pages' like: "2,4,7-9"
    1-based page numbers.
    """
    if not file.filename.lower().endswith(".pdf"):
        return JSONResponse(
            {"error": "Please upload a PDF file."},
            status_code=400
        )

    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total_pages = len(reader.pages)

        pages_to_delete = parse_pages_to_delete(pages, total_pages)

        if not pages_to_delete:
            return JSONResponse(
                {"error": "No valid pages to delete."},
                status_code=400
            )

        if len(pages_to_delete) >= total_pages:
            return JSONResponse(
                {"error": "Cannot delete all pages."},
                status_code=400
            )

        writer = PdfWriter()

        for idx in range(total_pages):
            page_number = idx + 1  # 1-based
            if page_number not in pages_to_delete:
                writer.add_page(reader.pages[idx])

        output_stream = io.BytesIO()
        writer.write(output_stream)
        output_stream.seek(0)

        return StreamingResponse(
            output_stream,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=deleted-pages.pdf"}
        )

    except Exception as e:
        return JSONResponse(
            {"error": f"Failed to delete pages: {str(e)}"},
            status_code=500
        )
