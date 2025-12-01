from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io

app = FastAPI(
    title="ToolSonics Backend",
    version="2.0",
    description="PDF Tools API for ToolSonics"
)

# =======================
# CORS (GitHub Allowed)
# =======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],     # later only domain add kar sakte ho
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ToolSonics Backend Running Successfully!"}

# =========================================================
# 1️⃣ MERGE PDF
# =========================================================
@app.post("/pdf/merge")
async def merge_pdfs(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        return JSONResponse({"error": "Upload at least 2 PDF files."}, status_code=400)

    merger = PdfMerger()

    try:
        for f in files:
            if not f.filename.endswith(".pdf"):
                return JSONResponse({"error": "Only PDF allowed."}, status_code=400)

            content = await f.read()
            merger.append(io.BytesIO(content))

        output = io.BytesIO()
        merger.write(output)
        merger.close()
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": "Merge failed: " + str(e)}, status_code=500)


# =========================================================
# 2️⃣ SPLIT PDF (BY PAGE RANGE)
# =========================================================
@app.post("/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...)
):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF file."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        total = len(reader.pages)

        if start_page < 1 or end_page < 1 or start_page > end_page:
            return JSONResponse({"error": "Invalid page range."}, status_code=400)

        if end_page > total:
            return JSONResponse({"error": f"PDF has only {total} pages."}, status_code=400)

        for i in range(start_page - 1, end_page):
            writer.add_page(reader.pages[i])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=split.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": "Split failed: " + str(e)}, status_code=500)


# =========================================================
# Helper: For DELETE + ROTATE pages
# =========================================================
def parse_pages(pages_str: str, total_pages: int):
    pages = set()

    for part in pages_str.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            a, b = part.split("-")
            a, b = int(a), int(b)
            if a > b:
                a, b = b, a
            for i in range(a, b + 1):
                if 1 <= i <= total_pages:
                    pages.add(i)
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p)
            except:
                pass

    return pages


# =========================================================
# 3️⃣ DELETE PAGES FROM PDF
# =========================================================
@app.post("/pdf/delete-pages")
async def delete_pages(
    file: UploadFile = File(...),
    pages: str = Form(...)
):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload a valid PDF."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()
        total = len(reader.pages)

        pages_to_delete = parse_pages(pages, total)

        if not pages_to_delete:
            return JSONResponse({"error": "No valid pages to delete."}, status_code=400)

        if len(pages_to_delete) >= total:
            return JSONResponse({"error": "Cannot delete all pages."}, status_code=400)

        for i in range(total):
            if (i + 1) not in pages_to_delete:
                writer.add_page(reader.pages[i])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=deleted-pages.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": "Delete failed: " + str(e)}, status_code=500)


# =========================================================
# 4️⃣ ROTATE PAGES IN PDF
# =========================================================
@app.post("/pdf/rotate-pages")
async def rotate_pages(
    file: UploadFile = File(...),
    rotation: int = Form(...),      # 90, 180, 270
    pages: str = Form("")           # blank -> all pages
):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)

        if rotation not in (90, 180, 270):
            return JSONResponse({"error": "Rotation must be 90,180,270."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()
        total = len(reader.pages)

        # if no pages → rotate ALL pages
        if pages.strip() == "":
            rotate_pages = set(range(1, total + 1))
        else:
            rotate_pages = parse_pages(pages, total)

        if not rotate_pages:
            return JSONResponse({"error": "No valid pages to rotate."}, status_code=400)

        for i in range(total):
            page_number = i + 1
            page = reader.pages[i]

            if page_number in rotate_pages:
                page.rotate(rotation)

            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=rotated.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": "Rotate failed: " + str(e)}, status_code=500)
