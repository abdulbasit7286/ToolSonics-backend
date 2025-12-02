from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import io

from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, letter

app = FastAPI(title="ToolSonics Backend", version="1.0")

# =============== CORS ============
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "ok", "message": "ToolSonics backend running"}


# =========== HELPER: parse pages like 1,3,5-7 ===========
def parse_pages(pages_str: str, total_pages: int):
    pages = set()
    for part in pages_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            s, e = part.split("-")
            s, e = int(s), int(e)
            if s > e:
                s, e = e, s
            for i in range(s, e + 1):
                if 1 <= i <= total_pages:
                    pages.add(i)
        else:
            if part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p)
    return pages


# =========================================================
# 1) MERGE PDF
# =========================================================
@app.post("/pdf/merge")
async def merge_pdf(files: List[UploadFile] = File(...)):
    if len(files) < 2:
        return JSONResponse({"error": "Upload at least 2 PDF files."}, status_code=400)

    merger = PdfMerger()
    try:
        for f in files:
            if not f.filename.lower().endswith(".pdf"):
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
        return JSONResponse({"error": f"Merge failed: {e}"}, status_code=500)


# =========================================================
# 2) SPLIT PDF
# =========================================================
@app.post("/pdf/split")
async def split_pdf(
    file: UploadFile = File(...),
    start_page: int = Form(...),
    end_page: int = Form(...)
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF file."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        if start_page < 1 or end_page < 1 or start_page > end_page or end_page > total:
            return JSONResponse({"error": "Invalid page range."}, status_code=400)

        writer = PdfWriter()
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
        return JSONResponse({"error": f"Split failed: {e}"}, status_code=500)


# =========================================================
# 3) DELETE PAGES
# =========================================================
@app.post("/pdf/delete-pages")
async def delete_pages(
    file: UploadFile = File(...),
    pages: str = Form(...)
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)
        to_delete = parse_pages(pages, total)

        if not to_delete:
            return JSONResponse({"error": "No valid pages to delete."}, status_code=400)
        if len(to_delete) >= total:
            return JSONResponse({"error": "Cannot delete all pages."}, status_code=400)

        writer = PdfWriter()
        for i in range(total):
            if (i + 1) not in to_delete:
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
        return JSONResponse({"error": f"Delete failed: {e}"}, status_code=500)


# =========================================================
# 4) ROTATE PAGES
# =========================================================
@app.post("/pdf/rotate-pages")
async def rotate_pages(
    file: UploadFile = File(...),
    rotation: int = Form(...),   # 90, 180, 270
    pages: str = Form("")        # "" => all pages
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)

        if rotation not in (90, 180, 270):
            return JSONResponse({"error": "Rotation must be 90, 180, or 270."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        if pages.strip():
            rotate_set = parse_pages(pages, total)
        else:
            rotate_set = set(range(1, total + 1))

        if not rotate_set:
            return JSONResponse({"error": "No valid pages to rotate."}, status_code=400)

        writer = PdfWriter()
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
        return JSONResponse({"error": f"Rotate failed: {e}"}, status_code=500)


# =========================================================
# 5) REORDER PAGES
# =========================================================
@app.post("/pdf/reorder-pages")
async def reorder_pages(
    file: UploadFile = File(...),
    order: str = Form(...)
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        try:
            order_list = [int(x.strip()) for x in order.split(",") if x.strip()]
        except:
            return JSONResponse({"error": "Invalid order format."}, status_code=400)

        if len(order_list) != total:
            return JSONResponse({"error": f"Order must have exactly {total} numbers."}, status_code=400)
        if any(p < 1 or p > total for p in order_list):
            return JSONResponse({"error": "Page numbers out of range."}, status_code=400)

        writer = PdfWriter()
        for p in order_list:
            writer.add_page(reader.pages[p - 1])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=reordered.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Reorder failed: {e}"}, status_code=500)


# =========================================================
# 6) PROTECT PDF (ADD PASSWORD)
# =========================================================
@app.post("/pdf/protect")
async def protect_pdf(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)
        if not password:
            return JSONResponse({"error": "Password required."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        for page in reader.pages:
            writer.add_page(page)

        writer.encrypt(password)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=protected.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Protect failed: {e}"}, status_code=500)


# =========================================================
# 7) UNLOCK PDF (REMOVE PASSWORD)
# =========================================================
@app.post("/pdf/unlock")
async def unlock_pdf(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))

        if reader.is_encrypted:
            try:
                reader.decrypt(password)
            except Exception:
                return JSONResponse({"error": "Wrong password or cannot decrypt."}, status_code=400)

        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=unlocked.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Unlock failed: {e}"}, status_code=500)


# =========================================================
# 8) ADD PAGE NUMBERS (simple text annotation bottom-center)
# =========================================================
@app.post("/pdf/add-page-numbers")
async def add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center")   # frontend se aa raha hai, abhi ignore karenge
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()
        total = len(reader.pages)

        # NOTE: PyPDF2 se proper text draw karna easy nahi,
        # isliye abhi hum sirf metadata style annotation use kar rahe.
        # Behavior PDF viewer pe depend karega.
        for idx, page in enumerate(reader.pages):
            page_number = idx + 1
            page.add_annotation({
                "/Type": "/Annot",
                "/Subtype": "/FreeText",
                "/Rect": [40, 20, 200, 40],
                "/Contents": f"Page {page_number}/{total}"
            })
            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=page-numbered.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Add page numbers failed: {e}"}, status_code=500)


# =========================================================
# 9) ADD TEXT WATERMARK (very simple annotation)
# =========================================================
@app.post("/pdf/watermark")
async def watermark_pdf(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("center"),
    opacity: float = Form(0.4),
    rotation: int = Form(45)
):
    try:
        if not file.filename.lower().endswith(".pdf"):
            return JSONResponse({"error": "Upload a PDF."}, status_code=400)
        if not text:
            return JSONResponse({"error": "Watermark text required."}, status_code=400)

        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        writer = PdfWriter()

        # Yaha hum sirf FreeText annotation add kar rahe.
        # Full graphic watermark ke liye reportlab ke saath merge karna padega (advanced).
        for page in reader.pages:
            page.add_annotation({
                "/Type": "/Annot",
                "/Subtype": "/FreeText",
                "/Rect": [100, 400, 400, 450],
                "/Contents": text
            })
            writer.add_page(page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=watermarked.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Watermark failed: {e}"}, status_code=500)


# =========================================================
# 10) TEXT → PDF (simple, ignore extra options for now)
# =========================================================
@app.post("/pdf/text-to-pdf")
async def text_to_pdf(
    text: str = Form(...),
    title: str = Form(""),
    font_size: int = Form(12),
    alignment: str = Form("left")
):
    try:
        if not text.strip():
            return JSONResponse({"error": "Text is empty."}, status_code=400)

        output = io.BytesIO()
        c = canvas.Canvas(output, pagesize=A4)

        width, height = A4
        y = height - 80

        if title.strip():
            c.setFont("Helvetica-Bold", font_size + 2)
            c.drawString(50, y, title.strip())
            y -= 30

        c.setFont("Helvetica", font_size)

        lines = text.split("\n")
        for line in lines:
            line = line.rstrip()
            if y < 50:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", font_size)

            if alignment == "center":
                text_width = c.stringWidth(line, "Helvetica", font_size)
                x = (width - text_width) / 2
            elif alignment == "right":
                text_width = c.stringWidth(line, "Helvetica", font_size)
                x = width - text_width - 50
            else:
                x = 50

            c.drawString(x, y, line)
            y -= (font_size + 4)

        c.save()
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=text.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Text to PDF failed: {e}"}, status_code=500)


# =========================================================
# 11) IMAGES → PDF
# =========================================================
@app.post("/pdf/images-to-pdf")
async def images_to_pdf(
    images: List[UploadFile] = File(...),
    page_size: str = Form("fit"),
    orientation: str = Form("portrait"),
    margin: int = Form(0)
):
    try:
        if not images:
            return JSONResponse({"error": "Upload at least 1 image."}, status_code=400)

        pil_images = []
        for img in images:
            img_bytes = await img.read()
            pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            pil_images.append(pil)

        if not pil_images:
            return JSONResponse({"error": "No valid images."}, status_code=400)

        # Simple: just join images into PDF pages same size as image.
        output = io.BytesIO()
        first = pil_images[0]
        rest = pil_images[1:]
        first.save(output, format="PDF", save_all=True, append_images=rest)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=images.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Images to PDF failed: {e}"}, status_code=500)


# =========================================================
# 12) CSV → EXCEL
# =========================================================
@app.post("/convert/csv-to-excel")
async def csv_to_excel(file: UploadFile = File(...)):
    try:
        if not file.filename.lower().endswith(".csv"):
            return JSONResponse({"error": "Upload a .csv file."}, status_code=400)

        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))

        output = io.BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=converted.xlsx"}
        )
    except Exception as e:
        return JSONResponse({"error": f"CSV to Excel failed: {e}"}, status_code=500)


# =========================================================
# 13) EXCEL → CSV
# =========================================================
@app.post("/convert/excel-to-csv")
async def excel_to_csv(file: UploadFile = File(...)):
    try:
        if not (file.filename.lower().endswith(".xlsx") or file.filename.lower().endswith(".xls")):
            return JSONResponse({"error": "Upload an Excel file (.xlsx/.xls)."}, status_code=400)

        content = await file.read()
        df = pd.read_excel(io.BytesIO(content))

        output = io.BytesIO()
        df.to_csv(output, index=False)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=converted.csv"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Excel to CSV failed: {e}"}, status_code=500)
