from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import io
from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
import pandas as pd

app = FastAPI(title="ToolSonics Backend v5.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "ToolSonics Backend Running Successfully!"}


# -------------------------------------------------------------
# HELPER: Parse Pages (like "1,3,5-9")
# -------------------------------------------------------------
def parse_pages(pages_str: str, total_pages: int):
    pages = set()
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            s, e = part.split("-")
            s, e = int(s), int(e)
            for i in range(s, e + 1):
                if 1 <= i <= total_pages:
                    pages.add(i)
        else:
            if part.isdigit():
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p)
    return pages


# -------------------------------------------------------------
# 1) MERGE PDF
# -------------------------------------------------------------
@app.post("/pdf/merge")
async def merge_pdf(files: List[UploadFile] = File(...)):
    merger = PdfMerger()
    for f in files:
        content = await f.read()
        merger.append(io.BytesIO(content))

    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)

    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=merged.pdf"})


# -------------------------------------------------------------
# 2) SPLIT PDF
# -------------------------------------------------------------
@app.post("/pdf/split")
async def split_pdf(file: UploadFile = File(...), start_page: int = Form(...), end_page: int = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()

    for i in range(start_page - 1, end_page):
        writer.add_page(reader.pages[i])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=split.pdf"})


# -------------------------------------------------------------
# 3) DELETE PAGES
# -------------------------------------------------------------
@app.post("/pdf/delete-pages")
async def delete_pages(file: UploadFile = File(...), pages: str = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()
    total = len(reader.pages)

    delete_set = parse_pages(pages, total)

    for i in range(total):
        if (i + 1) not in delete_set:
            writer.add_page(reader.pages[i])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=deleted.pdf"})


# -------------------------------------------------------------
# 4) ROTATE PAGES
# -------------------------------------------------------------
@app.post("/pdf/rotate-pages")
async def rotate_pages(file: UploadFile = File(...), rotation: int = Form(...), pages: str = Form("")):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()

    total = len(reader.pages)
    rotate_set = parse_pages(pages, total) if pages.strip() else set(range(1, total + 1))

    for i in range(total):
        page = reader.pages[i]
        if i + 1 in rotate_set:
            page.rotate(rotation)
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=rotated.pdf"})


# -------------------------------------------------------------
# 5) REORDER PAGES
# -------------------------------------------------------------
@app.post("/pdf/reorder-pages")
async def reorder_pages(file: UploadFile = File(...), order: str = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()
    total = len(reader.pages)

    order_list = [int(x) for x in order.split(",")]

    for page_no in order_list:
        writer.add_page(reader.pages[page_no - 1])

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=reordered.pdf"})


# -------------------------------------------------------------
# 6) PROTECT PDF (ADD PASSWORD)
# -------------------------------------------------------------
@app.post("/pdf/protect")
async def protect_pdf(file: UploadFile = File(...), password: str = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    writer.encrypt(password)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, headers={
        "Content-Disposition": "attachment; filename=protected.pdf"
    })


# -------------------------------------------------------------
# 7) UNLOCK PDF (REMOVE PASSWORD)
# -------------------------------------------------------------
@app.post("/pdf/unlock")
async def unlock_pdf(file: UploadFile = File(...), password: str = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))

    if reader.is_encrypted:
        reader.decrypt(password)

    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output, headers={
        "Content-Disposition": "attachment; filename=unlocked.pdf"
    })


# -------------------------------------------------------------
# 8) ADD WATERMARK (TEXT)
# -------------------------------------------------------------
@app.post("/pdf/watermark")
async def watermark_pdf(file: UploadFile = File(...), text: str = Form(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()

    for page in reader.pages:
        page.add_annotation({
            "/Type": "/Annot",
            "/Subtype": "/FreeText",
            "/Contents": text,
            "/Rect": [50, 50, 300, 100]
        })
        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output,
                             headers={"Content-Disposition": "attachment; filename=watermarked.pdf"})


# -------------------------------------------------------------
# 9) ADD PAGE NUMBERS
# -------------------------------------------------------------
@app.post("/pdf/add-page-numbers")
async def add_page_numbers(file: UploadFile = File(...)):
    content = await file.read()
    reader = PdfReader(io.BytesIO(content))
    writer = PdfWriter()
    total = len(reader.pages)

    for i in range(total):
        page = reader.pages[i]

        page.add_annotation({
            "/Type": "/Annot",
            "/Subtype": "/FreeText",
            "/Contents": f"Page {i+1}/{total}",
            "/Rect": [50, 20, 200, 40]
        })

        writer.add_page(page)

    output = io.BytesIO()
    writer.write(output)
    output.seek(0)

    return StreamingResponse(output,
        headers={"Content-Disposition": "attachment; filename=page-numbered.pdf"})


# -------------------------------------------------------------
# 10) TEXT → PDF
# -------------------------------------------------------------
@app.post("/pdf/text-to-pdf")
async def text_to_pdf(text: str = Form(...)):
    from reportlab.pdfgen import canvas
    output = io.BytesIO()
    c = canvas.Canvas(output)
    y = 800

    for line in text.split("\n"):
        c.drawString(50, y, line)
        y -= 20

    c.save()
    output.seek(0)

    return StreamingResponse(output,
        headers={"Content-Disposition": "attachment; filename=text.pdf"})


# -------------------------------------------------------------
# 11) IMAGE(S) → PDF
# -------------------------------------------------------------
@app.post("/pdf/images-to-pdf")
async def images_to_pdf(files: List[UploadFile] = File(...)):
    images = []

    for file in files:
        img = Image.open(io.BytesIO(await file.read())).convert("RGB")
        images.append(img)

    output = io.BytesIO()
    images[0].save(output, save_all=True, append_images=images[1:], format="PDF")
    output.seek(0)

    return StreamingResponse(output,
        headers={"Content-Disposition": "attachment; filename=images.pdf"})


# -------------------------------------------------------------
# 12) CSV → EXCEL
# -------------------------------------------------------------
@app.post("/csv/to-excel")
async def csv_to_excel(file: UploadFile = File(...)):
    df = pd.read_csv(io.BytesIO(await file.read()))

    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return StreamingResponse(output,
        headers={"Content-Disposition": "attachment; filename=converted.xlsx"})


# -------------------------------------------------------------
# 13) EXCEL → CSV
# -------------------------------------------------------------
@app.post("/excel/to-csv")
async def excel_to_csv(file: UploadFile = File(...)):
    df = pd.read_excel(io.BytesIO(await file.read()))

    output = io.BytesIO()
    df.to_csv(output, index=False)
    output.seek(0)

    return StreamingResponse(output,
        headers={"Content-Disposition": "attachment; filename=converted.csv"})
