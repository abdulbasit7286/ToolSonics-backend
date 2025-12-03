from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import io

from PyPDF2 import PdfMerger, PdfReader, PdfWriter
from PIL import Image
import pandas as pd

# For page numbers (overlay using ReportLab)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter


app = FastAPI(title="ToolSonics Backend", version="2.0")


# -----------------------------------------------------------
# CORS ENABLE
# -----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"status": "ok", "message": "ToolSonics backend running"}


# -----------------------------------------------------------
# PARSE PAGE RANGES (ex: 1,3,5-7)
# -----------------------------------------------------------
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


# -----------------------------------------------------------
# 1) MERGE PDF
# -----------------------------------------------------------
@app.post("/pdf/merge")
async def merge_pdf(files: List[UploadFile] = File(...)):
    try:
        merger = PdfMerger()
        for f in files:
            content = await f.read()
            merger.append(io.BytesIO(content))

        output = io.BytesIO()
        merger.write(output)
        output.seek(0)
        merger.close()

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=merged.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": f"Merge failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 2) SPLIT PDF
# -----------------------------------------------------------
@app.post("/pdf/split")
async def split_pdf(file: UploadFile = File(...),
                    start_page: int = Form(...),
                    end_page: int = Form(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

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


# -----------------------------------------------------------
# 3) DELETE PAGES
# -----------------------------------------------------------
@app.post("/pdf/delete-pages")
async def delete_pages(file: UploadFile = File(...),
                       pages: str = Form(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        delete_set = parse_pages(pages, total)

        writer = PdfWriter()
        for i in range(total):
            if (i + 1) not in delete_set:
                writer.add_page(reader.pages[i])

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=deleted.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Delete failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 4) ROTATE
# -----------------------------------------------------------
@app.post("/pdf/rotate-pages")
async def rotate_pages(
    file: UploadFile = File(...),
    rotation: int = Form(...),
    pages: str = Form("")
):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        if pages.strip():
            rotate_set = parse_pages(pages, total)
        else:
            rotate_set = set(range(1, total + 1))

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


# -----------------------------------------------------------
# 5) REORDER
# -----------------------------------------------------------
@app.post("/pdf/reorder-pages")
async def reorder_pages(file: UploadFile = File(...),
                        order: str = Form(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        order_list = [int(x.strip()) for x in order.split(",") if x.strip()]

        if len(order_list) != total:
            return JSONResponse({"error": f"Order must contain {total} numbers."}, status_code=400)

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


# -----------------------------------------------------------
# 6) PROTECT
# -----------------------------------------------------------
@app.post("/pdf/protect")
async def protect_pdf(file: UploadFile = File(...),
                      password: str = Form(...)):
    try:
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


# -----------------------------------------------------------
# 7) UNLOCK
# -----------------------------------------------------------
@app.post("/pdf/unlock")
async def unlock_pdf(file: UploadFile = File(...),
                     password: str = Form(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))

        if reader.is_encrypted:
            reader.decrypt(password)

        writer = PdfWriter()
        for p in reader.pages:
            writer.add_page(p)

        out = io.BytesIO()
        writer.write(out)
        out.seek(0)

        return StreamingResponse(
            out,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=unlocked.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Unlock failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 8) ADD PAGE NUMBERS (FIXED)
# -----------------------------------------------------------
@app.post("/pdf/add-page-numbers")
async def add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center")
):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))
        total = len(reader.pages)

        writer = PdfWriter()

        for page_num in range(total):
            original_page = reader.pages[page_num]

            # Create temp canvas
            layer_bytes = io.BytesIO()
            c = canvas.Canvas(layer_bytes, pagesize=letter)

            text = f"{page_num+1} / {total}"

            if position == "bottom-left":
                x, y = 40, 20
            elif position == "bottom-right":
                x, y = 520, 20
            else:
                x, y = 275, 20

            c.setFont("Helvetica", 12)
            c.drawString(x, y, text)
            c.save()
            layer_bytes.seek(0)

            overlay = PdfReader(layer_bytes).pages[0]
            original_page.merge_page(overlay)
            writer.add_page(original_page)

        output = io.BytesIO()
        writer.write(output)
        output.seek(0)

        return StreamingResponse(
            output,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=numbered.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": f"Add page numbers failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 9) WATERMARK TEXT
# -----------------------------------------------------------
@app.post("/pdf/watermark")
async def watermark_pdf(file: UploadFile = File(...),
                        text: str = Form(...)):
    try:
        content = await file.read()
        reader = PdfReader(io.BytesIO(content))

        writer = PdfWriter()

        for page in reader.pages:
            layer_buf = io.BytesIO()
            c = canvas.Canvas(layer_buf, pagesize=letter)
            c.setFont("Helvetica", 40)
            c.setFillGray(0.5, 0.5)
            c.saveState()
            c.rotate(45)
            c.drawString(150, 0, text)
            c.restoreState()
            c.save()
            layer_buf.seek(0)

            overlay = PdfReader(layer_buf).pages[0]
            page.merge_page(overlay)
            writer.add_page(page)

        out = io.BytesIO()
        writer.write(out)
        out.seek(0)

        return StreamingResponse(
            out,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=watermarked.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Watermark failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 10) TEXT → PDF
# -----------------------------------------------------------
@app.post("/pdf/text-to-pdf")
async def text_to_pdf(
    text: str = Form(...),
    title: str = Form(""),
    font_size: int = Form(12),
    alignment: str = Form("left")
):
    try:
        out = io.BytesIO()
        c = canvas.Canvas(out, pagesize=letter)

        width, height = letter
        y = height - 60

        if title:
            c.setFont("Helvetica-Bold", font_size + 2)
            c.drawString(50, y, title)
            y -= 30

        c.setFont("Helvetica", font_size)

        for line in text.split("\n"):
            if y < 60:
                c.showPage()
                y = height - 60

            if alignment == "center":
                x = (width - c.stringWidth(line)) / 2
            elif alignment == "right":
                x = width - c.stringWidth(line) - 50
            else:
                x = 50

            c.drawString(x, y, line)
            y -= (font_size + 4)

        c.save()
        out.seek(0)

        return StreamingResponse(
            out,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=text.pdf"}
        )

    except Exception as e:
        return JSONResponse({"error": f"Text to PDF failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 11) IMAGES → PDF
# -----------------------------------------------------------
@app.post("/pdf/images-to-pdf")
async def images_to_pdf(images: List[UploadFile] = File(...)):
    try:
        pil_imgs = []
        for img in images:
            data = await img.read()
            pil = Image.open(io.BytesIO(data)).convert("RGB")
            pil_imgs.append(pil)

        out = io.BytesIO()
        pil_imgs[0].save(out, format="PDF", save_all=True, append_images=pil_imgs[1:])
        out.seek(0)

        return StreamingResponse(
            out,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=images.pdf"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Images to PDF failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 12) CSV → EXCEL
# -----------------------------------------------------------
@app.post("/convert/csv-to-excel")
async def csv_to_excel(file: UploadFile = File(...)):
    try:
        df = pd.read_csv(io.BytesIO(await file.read()))
        out = io.BytesIO()
        df.to_excel(out, index=False)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=converted.xlsx"}
        )
    except Exception as e:
        return JSONResponse({"error": f"CSV to Excel failed: {e}"}, status_code=500)


# -----------------------------------------------------------
# 13) EXCEL → CSV
# -----------------------------------------------------------
@app.post("/convert/excel-to-csv")
async def excel_to_csv(file: UploadFile = File(...)):
    try:
        df = pd.read_excel(io.BytesIO(await file.read()))
        out = io.BytesIO()
        df.to_csv(out, index=False)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=converted.csv"}
        )
    except Exception as e:
        return JSONResponse({"error": f"Excel to CSV failed: {e}"}, status_code=500)
