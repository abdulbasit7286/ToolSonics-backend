from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
import io

app = FastAPI(
    title="ToolSonics PDF Backend",
    version="3.0",
    description="All PDF tools backend: Merge, Split, Delete, Rotate, Reorder"
)

# CORS ALLOW ALL (GitHub Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "ToolSonics Backend Running Successfully!"}

# =========================================================
# 1️⃣ MERGE PDF
# =========================================================
@app.post("/pdf/merge")
async def merge_pdf(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        return JSONResponse({"error": "Upload at least 2 PDF files."}, status_code=400)
    
    merger = PdfMerger()
    try:
        for f in files:
            if not f.filename.endswith(".pdf"):
                return JSONResponse({"error": "Only PDF files allowed."}, status_code=400)
            
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
# 2️⃣ SPLIT PDF (PAGE RANGE)
# =========================================================
@app.post("/pdf/split")
async def split_pdf(file: UploadFile = File(...), start_page: int = Form(...), end_page: int = Form(...)):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload PDF only."}, status_code=400)

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
# Helper - Parse pages like "2,4,7-9"
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
            for x in range(a, b + 1):
                if 1 <= x <= total_pages:
                    pages.add(x)
        else:
            try:
                x = int(part)
                if 1 <= x <= total_pages:
                    pages.add(x)
            except:
                pass
    return pages

# =========================================================
# 3️⃣ DELETE PAGES
# =========================================================
@app.post("/pdf/delete-pages")
async def delete_pdf_pages(file: UploadFile = File(...), pages: str = Form(...)):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload a valid PDF."}, status_code=400)

        pdf_bytes = await file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        total = len(reader.pages)
        delete_set = parse_pages(pages, total)

        if not delete_set:
            return JSONResponse({"error": "No valid pages."}, status_code=400)

        if len(delete_set) >= total:
            return JSONResponse({"error": "Cannot delete all pages."}, status_code=400)

        for i in range(total):
            if (i + 1) not in delete_set:
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
# 4️⃣ ROTATE PAGES
# =========================================================
@app.post("/pdf/rotate-pages")
async def rotate_pdf_pages(file: UploadFile = File(...), rotation: int = Form(...), pages: str = Form("")):
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload PDF only."}, status_code=400)

        if rotation not in (90, 180, 270):
            return JSONResponse({"error": "Rotation must be 90, 180, 270."}, status_code=400)

        pdf_bytes = await file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        total = len(reader.pages)

        if pages.strip() == "":
            rotate_set = set(range(1, total + 1))
        else:
            rotate_set = parse_pages(pages, total)

        if not rotate_set:
            return JSONResponse({"error": "Invalid pages."}, status_code=400)

        for i in range(total):
            page = reader.pages[i]
            if (i + 1) in rotate_set:
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
        return JSONResponse({"error": "Rotation failed: " + str(e)}, status_code=500)

# =========================================================
# 5️⃣ REORDER PAGES (NEW)
# =========================================================
@app.post("/pdf/reorder-pages")
async def reorder_pdf_pages(file: UploadFile = File(...), order: str = Form(...)):
    """
    Example input:
    order = "3,1,4,2"
    Means: page 3 -> first, page 1 -> second, page 4 -> third, page 2 -> fourth
    """
    try:
        if not file.filename.endswith(".pdf"):
            return JSONResponse({"error": "Upload PDF only."}, status_code=400)

        pdf_bytes = await file.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()
        total = len(reader.pages)

        # Convert order string → list
        try:
            new_order = [int(x.strip()) for x in order.split(",") if x.strip().isdigit()]
        except:
            return JSONResponse({"error": "Invalid format. Use comma-separated numbers."}, status_code=400)

        # Validate
        if len(new_order) != total:
            return JSONResponse({"error": f"Order must contain exactly {total} pages."}, status_code=400)

        if any(x < 1 or x > total for x in new_order):
            return JSONResponse({"error": "Page numbers out of range."}, status_code=400)

        # Reorder pages
        for page_num in new_order:
            writer.add_page(reader.pages[page_num - 1])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=reordered.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": "Reorder failed: " + str(e)}, status_code=500)
