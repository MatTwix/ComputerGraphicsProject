import streamlit as st
from pathlib import Path
from PIL import Image
import csv
import uuid
import shutil
from process import (
    processImageFile,
    DEFAULT_DPI,
    DEFAULT_THRESHOLD,
    DEFAULT_OUTPUT_FROMAT,
    DEFAULT_JPEG_QUALITY,
    A4_IN,
)

st.set_page_config(page_title="A4 Print Prep", layout="wide")
st.title("A4 Print Prep")

with st.expander("📝 О программе и параметрах оптимизации"):
    st.markdown("""
    **A4 Print Prep** - программа для подготовки изображений к печати на формате A4.
    
    **Применяемые оптимизации для печати:**
    
    - **DPI (Dots Per Inch)**: {0} - высокое разрешение для качественной печати
    - **Цветовая модель**: CMYK - оптимальная для полиграфической печати
    - **Качество JPEG**: {1}% - высокое качество с минимальным сжатием
    - **Сжатие TIFF**: LZW - беспотерьное сжатие
    - **Масштабирование**: Пропорциональное с сохранением соотношения сторон
    - **Поля**: Белые поля вокруг изображения
    - **Формат**: A4 ({2:.2f}×{3:.2f} дюймов)
    
    **Контроль качества**: Изображения с коэффициентом увеличения больше {4} отбраковываются
    """.format(DEFAULT_DPI, DEFAULT_JPEG_QUALITY, A4_IN[0], A4_IN[1], DEFAULT_THRESHOLD))

out_dir = Path("output")
out_dir.mkdir(exist_ok=True)

if "preview_images" not in st.session_state:
    st.session_state.preview_images = []  # список (tmp_path, имя файла)
if "processed_images" not in st.session_state:
    st.session_state.processed_images = []  # список (outPath, имя файла)

uploaded_files = st.file_uploader(
    "Выберите изображения",
    type=["jpg", "jpeg", "png", "tif", "tiff", "bmp"],
    accept_multiple_files=True,
)

if uploaded_files:
    existing_files = {fname for _, fname in st.session_state.preview_images}
    
    for f in uploaded_files:
        if f.name not in existing_files:
            tmp_path = out_dir / f"{uuid.uuid4()}_{f.name}"
            with open(tmp_path, "wb") as buf:
                buf.write(f.read())
            st.session_state.preview_images.append((tmp_path, f.name))

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

if st.session_state.preview_images:
    col_header, col_count, col_clear = st.columns([2, 1, 1])
    with col_header:
        st.subheader("Превью исходных файлов")
    with col_count:
        st.metric("Файлов загружено", len(st.session_state.preview_images))
    with col_clear:
        if st.button("🗑️ Очистить всё"):
            for p, _ in st.session_state.preview_images:
                if p.exists():
                    p.unlink()
            st.session_state.preview_images = []
            st.session_state.processed_images = []
            st.rerun()
    for tmp_path, fname in st.session_state.preview_images:
        try:
            im = Image.open(tmp_path)
            im.thumbnail((200, 200))  # уменьшенное превью
            st.image(im, caption=fname, width=200)
        except Exception as e:
            st.error(f"Не удалось показать превью {fname}: {e}")

if st.button("🚀 Запустить обработку") and st.session_state.preview_images:
    reportRows = []
    progress = st.progress(0)
    total = len(st.session_state.preview_images)

    st.session_state.processed_images = []  # очищаем старые

    for i, (tmp_path, fname) in enumerate(st.session_state.preview_images, start=1):
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
            try:
                im_before = Image.open(tmp_path)
                im_before.thumbnail((250, 250))
                st.image(im_before, caption=f"До: {fname}", width=250)
            except Exception as e:
                st.error(f"Не удалось показать исходное {fname}: {e}")

        if res["status"] == "converted":
            with col_b:
                try:
                    im_after = Image.open(res["outPath"])
                    im_after.thumbnail((400, 400))  # большее превью после обработки
                    st.image(im_after, caption="После", width=400)
                except Exception as e:
                    st.error(f"Не удалось показать обработанное {fname}: {e}")

            st.session_state.processed_images.append((res["outPath"], fname))
            
            with st.expander(f"📊 Подробности обработки: {fname}"):
                col_info1, col_info2 = st.columns(2)
                
                with col_info1:
                    st.write("**Параметры обработки:**")
                    st.write(f"- DPI: {DEFAULT_DPI}")
                    st.write(f"- Цветовая модель: CMYK")
                    st.write(f"- Ориентация: {orientation}")
                    st.write(f"- Расположение: {placement}")
                    st.write(f"- Цвет полей: {border_color}")
                    
                with col_info2:
                    st.write("**Результат обработки:**")
                    st.write(f"- Коэфф. масштаба X: {res.get('scaleX', 0):.3f}")
                    st.write(f"- Коэфф. масштаба Y: {res.get('scaleY', 0):.3f}")
                    st.write(f"- Формат вывода: {out_format}")
                    if out_format.upper() == "JPEG":
                        st.write(f"- Качество JPEG: {DEFAULT_JPEG_QUALITY}%")
                    else:
                        st.write("- Сжатие TIFF: LZW")
                    
            st.success(f"✅ {fname} → {Path(res['outPath']).name}")
        else:
            st.error(f"{fname}: {res['reason']}")

        reportRows.append(
            [
                fname,
                res["status"],
                res.get("reason", ""),
                res.get("scaleX", 0),
                res.get("scaleY", 0),
                res.get("outPath", ""),
            ]
        )
        progress.progress(i / total)

    if st.session_state.processed_images:
        st.subheader("💾 Скачать обработанные файлы")
        
        col_metric1, col_metric2, col_metric3 = st.columns(3)
        with col_metric1:
            st.metric("Обработано файлов", len(st.session_state.processed_images))
        with col_metric2:
            st.metric("Формат вывода", out_format)
        with col_metric3:
            st.metric("DPI", f"{DEFAULT_DPI}")
        
        st.markdown("---")
        
        for outPath, fname in st.session_state.processed_images:
            st.download_button(
                f"💾 Скачать {fname}",
                data=open(outPath, "rb"),
                file_name=Path(outPath).name,
                mime="image/tiff" if out_format == "TIFF" else "image/jpeg",
            )

    reportPath = out_dir / "report.csv"
    with open(reportPath, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["source", "status", "details", "scaleX", "scaleY", "outPath"])
        w.writerows(reportRows)

    st.markdown("---")
    st.subheader("📈 Отчёт о процессе обработки")
    st.download_button(
        "📈 Скачать отчёт CSV",
        data=open(reportPath, "rb"),
        file_name="report.csv",
        mime="text/csv",
    )
