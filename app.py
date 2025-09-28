# app.py
import streamlit as st
from pathlib import Path
from PIL import Image
import csv
import uuid
from process import (
    processImageFile,
    DEFAULT_DPI,
    DEFAULT_THRESHOLD,
    DEFAULT_OUTPUT_FROMAT,
    DEFAULT_JPEG_QUALITY,
)

st.set_page_config(page_title="A4 Print Prep", layout="wide")

st.title("A4 Print Prep")

uploaded_files = st.file_uploader(
    "Выберите изображения",
    type=["jpg", "jpeg", "png", "tif", "tiff", "bmp"],
    accept_multiple_files=True,
)

col1, col2, col3 = st.columns(3)

with col1:
    orientation = st.selectbox("Ориентация", ["portrait", "landscape", "reverse"])
with col2:
    placement = st.selectbox("Расположение", ["center", "top", "bottom", "left", "right"])
with col3:
    out_format = st.selectbox("Формат", ["TIFF", "JPEG"])

threshold = st.slider("Порог отбраковки", 1.0, 10.0, DEFAULT_THRESHOLD, 0.1)

border_color = st.color_picker("Цвет полей", "#FFFFFF")
borderRGB = tuple(int(border_color.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4))

out_dir = Path("output")
out_dir.mkdir(exist_ok=True)

if st.button("🚀 Запустить обработку") and uploaded_files:
    reportRows = []
    progress = st.progress(0)
    total = len(uploaded_files)

    for i, f in enumerate(uploaded_files, start=1):
        tmp_path = out_dir / f"{uuid.uuid4()}_{f.name}"
        with open(tmp_path, "wb") as buf:
            buf.write(f.read())

        res = processImageFile(
            tmp_path,
            out_dir,
            dpi=DEFAULT_DPI,
            threshold=threshold,
            placement=placement,
            borderRGB=borderRGB,
            outFormat=out_format,
            jpegQuality=DEFAULT_JPEG_QUALITY,
            orientation=orientation,
        )

        col_a, col_b = st.columns(2)

        with col_a:
            st.image(str(tmp_path), caption=f"До: {f.name}", use_column_width=True)

        if res["status"] == "converted":
            with col_b:
                st.image(str(res["outPath"]), caption="После", use_column_width=True)

            st.success(f"{f.name} → {Path(res['outPath']).name}")
            st.download_button(
                "Скачать обработанный файл",
                data=open(res["outPath"], "rb"),
                file_name=Path(res["outPath"]).name,
                mime="image/tiff" if out_format == "TIFF" else "image/jpeg",
            )
        else:
            st.error(f"{f.name}: {res['reason']}")

        reportRows.append(
            [
                f.name,
                res["status"],
                res.get("reason", ""),
                res.get("scaleX", 0),
                res.get("scaleY", 0),
                res.get("outPath", ""),
            ]
        )
        progress.progress(i / total)

    reportPath = out_dir / "report.csv"
    with open(reportPath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "status", "details", "scaleX", "scaleY", "outPath"])
        w.writerows(reportRows)

    st.download_button(
        "Скачать отчёт CSV",
        data=open(reportPath, "rb"),
        file_name="report.csv",
        mime="text/csv",
    )