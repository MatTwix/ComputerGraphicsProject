import os
import csv
import math
from pathlib import Path
from PIL import Image, ImageCms
from PySide6 import QtWidgets, QtGui, QtCore
import sys

A4_IN = (8.2677165354, 11.6929133858)
DEFAULT_DPI = 300
DEFAULT_THRESHOLD = 2.0
DEFAULT_OUTPUT_FROMAT = 'TIFF'
DEFAULT_JPEG_QUALITY = 95

def pil2pixmap(im: Image.Image) -> QtGui.QPixmap:
    im = im.convert("RGBA")  # всегда RGBA
    data = im.tobytes("raw", "RGBA")
    qimage = QtGui.QImage(data, im.width, im.height, QtGui.QImage.Format_RGBA8888)
    return QtGui.QPixmap.fromImage(qimage)

def a4Pixels(dpi = DEFAULT_DPI, orientation='portrait'):
    w = round(A4_IN[0] * dpi)
    h = round(A4_IN[1] * dpi)
    if orientation == 'landscape':
        w, h = h, w
    return w, h

def needsRejection(srcH, srcW, targetW, targetH, threshold=DEFAULT_THRESHOLD):
    scaleX = targetW / srcW
    scaleY = targetH / srcH
    return (scaleX >= threshold) or (scaleY >= threshold), scaleX, scaleY

def fitAndPad(img: Image.Image, targetW: int, targetH: int, placement='center', borderRGB=(255, 255, 255)):
    srcW, srcH = img.size
    scale = min(targetW/srcW, targetH/srcH)

    newW = max(1, int(round(srcW * scale)))
    newH = max(1, int(round(srcH * scale)))
    resized = img.resize((newW, newH), Image.LANCZOS)

    canvas = Image.new('RGB', (targetW, targetH), borderRGB)

    if placement == 'center':
        x = (targetW - newW) // 2
        y = (targetH - newH) // 2
    elif placement == 'top':
        x = (targetW - newW) // 2
        y = 0
    elif placement == 'bottom':
        x = (targetW - newW) // 2
        y = targetH - newH 
    elif placement == 'left':
        x = 0
        y = (targetH - newH) // 2
    elif placement == 'right':
        x = targetW - newW
        y = (targetH - newH) // 2
    else:
        x = (targetW - newW) // 2
        y = (targetH - newH) // 2

    canvas.paste(resized, (x, y))
    return canvas, scale

def convertToCMYK(imageRGB: Image.Image, iccProfilePath = None):
    if iccProfilePath:
        try:
            srgbProfile = ImageCms.createProfile("sRGB")
            cmykProfile = ImageCms.ImageCmsProfile(iccProfilePath)
            imgConv = ImageCms.profileToProfile(imageRGB, srgbProfile, cmykProfile, outputMode='CMYK')
        except Exception as e:
            print("ICC conversion failed: ", e)
    return imageRGB.convert('CMYK')

def chooseOutputName(srcPath: Path, outDir: Path, fmt='TIFF'):
    base = srcPath.stem
    if fmt.upper() == 'JPEG':
        ext = '.jpg'
    elif fmt.upper() == 'TIFF':
        ext = '.tiff'
    else:
        ext = f'.{fmt.lower()}'
    return outDir / (base + ext)

from pathlib import Path
from PIL import Image

def processImageFile(
    srcPath: Path,
    outDir: Path,
    dpi=DEFAULT_DPI,
    threshold=DEFAULT_THRESHOLD,
    placement='center',
    borderRGB=(255, 255, 255),
    outFormat=DEFAULT_OUTPUT_FROMAT,
    jpegQuality=DEFAULT_JPEG_QUALITY,
    orientation='portrait',   # по умолчанию portrait
):
    # Целевая ширина/высота с учётом ориентации
    targetW, targetH = a4Pixels(dpi, orientation=orientation.lower())

    try:
        with Image.open(srcPath) as im:
            if orientation.lower() == "landscape" and im.height > im.width:
                im = im.rotate(90, expand=True)
            elif orientation.lower() == "reverse":
                im = im.rotate(180, expand=True)

            srcW, srcH = im.size
            rej, scaleX, scaleY = needsRejection(srcW, srcH, targetW, targetH, threshold)
            if rej:
                return {
                    'status': 'rejected',
                    'reason': f'scaleX={scaleX:.2f} or scaleY={scaleY:.2f} >= threshold {threshold}',
                    'scaleX': scaleX,
                    'scaleY': scaleY,
                }

            if im.mode not in ('RGB', "RGBA"):
                im = im.convert('RGB')

            # Масштабируем и вставляем в канву под нужную ориентацию
            canvas, usedScale = fitAndPad(im, targetW, targetH, placement=placement, borderRGB=borderRGB)

            final = convertToCMYK(canvas)
            outPath = chooseOutputName(srcPath, outDir, fmt=outFormat)

            saveKwargs = {'dpi': (dpi, dpi)}
            if outFormat.upper() == 'JPEG':
                saveKwargs['quality'] = jpegQuality
                final = final.convert("RGB")
                final.save(outPath, 'JPEG', **saveKwargs)
            else:
                final.save(outPath, 'TIFF', compression='tiff_lzw', **saveKwargs)

            return {
                'status': 'converted',
                'outPath': str(outPath),
                'scaleX': scaleX,
                'scaleY': scaleY,
            }
    except Exception as e:
        return {'status': 'error', 'reason': str(e)}
    
class MainWindow(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("A4 Print Prep")
        self.resize(1000, 600)
        layout = QtWidgets.QHBoxLayout(self)
        left = QtWidgets.QVBoxLayout()
        right = QtWidgets.QVBoxLayout()
        layout.addLayout(left, 2)
        layout.addLayout(right, 3)

        # Left: controls + file list
        btn_pick = QtWidgets.QPushButton("Выбрать входную папку")
        btn_pick.clicked.connect(self.pick_folder)
        self.inputLabel = QtWidgets.QLabel("Папка: —")
        self.lst = QtWidgets.QListWidget()
        self.lst.itemSelectionChanged.connect(self.show_preview)
        left.addWidget(btn_pick)
        left.addWidget(self.inputLabel)
        left.addWidget(self.lst)

        # Right: preview and settings
        self.previewBefore = QtWidgets.QLabel("До")
        self.previewBefore.setAlignment(QtCore.Qt.AlignCenter)
        self.previewBefore.setFixedHeight(250)
        self.previewAfter = QtWidgets.QLabel("После")
        self.previewAfter.setAlignment(QtCore.Qt.AlignCenter)
        self.previewAfter.setFixedHeight(250)

        previewLayout = QtWidgets.QHBoxLayout()
        previewLayout.addWidget(self.previewBefore)
        previewLayout.addWidget(self.previewAfter)
        right.addLayout(previewLayout)

        # settings
        form = QtWidgets.QFormLayout()
        self.borderColorBtn = QtWidgets.QPushButton("Цвет полей (нажать)")
        self.borderColorBtn.clicked.connect(self.pick_color)

        self.placementCombo = QtWidgets.QComboBox()
        self.placementCombo.addItems(['center', 'top', 'bottom', 'left', 'right'])

        self.thresholdSpin = QtWidgets.QDoubleSpinBox()
        self.thresholdSpin.setRange(1.0, 10.0)
        self.thresholdSpin.setSingleStep(0.1)
        self.thresholdSpin.setValue(DEFAULT_THRESHOLD)

        self.formatCombo = QtWidgets.QComboBox()
        self.formatCombo.addItems(['TIFF', 'JPEG'])

        # Новый параметр — ориентация
        self.orientationCombo = QtWidgets.QComboBox()
        self.orientationCombo.addItems(['Portrait', 'Landscape'])

        form.addRow("Цвет полей", self.borderColorBtn)
        form.addRow("Расположение", self.placementCombo)
        form.addRow("Порог отбраковки", self.thresholdSpin)
        form.addRow("В выходной формат", self.formatCombo)
        form.addRow("Ориентация", self.orientationCombo)
        right.addLayout(form)

        # actions
        self.btnRun = QtWidgets.QPushButton("Запустить обработку")
        self.btnRun.clicked.connect(self.runProcess)
        self.outDirLabel = QtWidgets.QLabel("Папка вывода: —")
        right.addWidget(self.outDirLabel)
        right.addWidget(self.btnRun)
        self.progress = QtWidgets.QProgressBar()
        right.addWidget(self.progress)

        # state
        self.inDir = None
        self.outDir = None
        self.borderRGB = (255, 255, 255)

        # Подключаем автообновление предпросмотра
        self.placementCombo.currentIndexChanged.connect(self.show_preview)
        self.thresholdSpin.valueChanged.connect(self.show_preview)
        self.formatCombo.currentIndexChanged.connect(self.show_preview)
        self.orientationCombo.currentIndexChanged.connect(self.show_preview)

    def pick_folder(self):
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку с изображениями")
        if d:
            self.inDir = Path(d)
            self.inputLabel.setText(f"Папка: {d}")
            self.lst.clear()
            for p in sorted(self.inDir.iterdir()):
                if p.is_file() and p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'):
                    self.lst.addItem(str(p.name))

    def pick_color(self):
        c = QtWidgets.QColorDialog.getColor()
        if c.isValid():
            self.borderRGB = (c.red(), c.green(), c.blue())
            self.borderColorBtn.setStyleSheet(f"background-color: {c.name()};")
            self.show_preview()  # обновляем превью сразу после выбора цвета

    def show_preview(self):
        sel = self.lst.selectedItems()
        if not sel or not self.inDir:
            return
        name = sel[0].text()
        p = self.inDir / name
        try:
            with Image.open(p) as im:
                # применяем ориентацию
                if self.orientationCombo.currentText() == "Landscape":
                    im = im.rotate(90, expand=True)

                T_W, T_H = 800, 1100
                before = im.copy()
                before.thumbnail((T_W // 2, T_H // 2), Image.LANCZOS)
                pix_before = pil2pixmap(before)
                self.previewBefore.setPixmap(
                    pix_before.scaled(self.previewBefore.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                )

                canvas, _ = fitAndPad(
                    im, T_W, T_H,
                    placement=self.placementCombo.currentText(),
                    borderRGB=self.borderRGB
                )
                pixAfter = pil2pixmap(canvas)
                self.previewAfter.setPixmap(
                    pixAfter.scaled(self.previewAfter.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                )
        except Exception as e:
            print("Ошибка предпросмотра:", e)

    def runProcess(self):
        if not self.inDir:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Выберите входную папку")
            return
        # choose output folder
        od = QtWidgets.QFileDialog.getExistingDirectory(self, "Выберите папку вывода (пустая или новая)")
        if not od:
            return
        self.outDir = Path(od)
        files = [self.inDir / it.text() for it in self.lst.selectedItems()] if self.lst.selectedItems() else [
            p for p in self.inDir.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')
        ]
        total = len(files)
        self.progress.setMaximum(total)
        reportRows = []
        for i, p in enumerate(files, start=1):
            res = processImageFile(
                p, self.outDir, dpi=DEFAULT_DPI, threshold=self.thresholdSpin.value(),
                placement=self.placementCombo.currentText(), borderRGB=self.borderRGB,
                outFormat=self.formatCombo.currentText(), jpegQuality=DEFAULT_JPEG_QUALITY,
                orientation=self.orientationCombo.currentText()
            )
            if res['status'] == 'converted':
                reportRows.append([str(p), 'converted', res.get('outPath', ''), f"{res.get('scaleX', 0):.2f}",
                                   f"{res.get('scaleY', 0):.2f}", ''])
            else:
                reportRows.append([str(p), res['status'], res.get('reason', ''), f"{res.get('scaleX', 0):.2f}",
                                   f"{res.get('scaleY', 0):.2f}", ''])
            self.progress.setValue(i)
            QtWidgets.QApplication.processEvents()
        # write report.csv
        reportPath = self.outDir / 'report.csv'
        with open(reportPath, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['source', 'status', 'details', 'scaleX', 'scaleY', 'outPath'])
            for r in reportRows:
                w.writerow(r)
        QtWidgets.QMessageBox.information(self, "Готово", f"Обработка завершена. Отчёт: {reportPath}")

def main():
    app = QtWidgets.QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()