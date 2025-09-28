from pathlib import Path
from PIL import Image, ImageCms

A4_IN = (8.2677165354, 11.6929133858)
DEFAULT_DPI = 300
DEFAULT_THRESHOLD = 2.0
DEFAULT_OUTPUT_FROMAT = 'TIFF'
DEFAULT_JPEG_QUALITY = 95

def a4Pixels(dpi=DEFAULT_DPI, orientation='portrait'):
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
    x = (targetW - newW) // 2
    y = (targetH - newH) // 2
    canvas.paste(resized, (x, y))
    return canvas, scale

def convertToCMYK(imageRGB: Image.Image, iccProfilePath=None):
    if iccProfilePath:
        try:
            srgbProfile = ImageCms.createProfile("sRGB")
            cmykProfile = ImageCms.ImageCmsProfile(iccProfilePath)
            return ImageCms.profileToProfile(imageRGB, srgbProfile, cmykProfile, outputMode="CMYK")
        except:
            pass
    return imageRGB.convert('CMYK')

def chooseOutputName(srcPath: Path, outDir: Path, fmt='TIFF'):
    base = Path(srcPath).stem
    ext = ".jpg" if fmt.upper() == "JPEG" else ".tiff"
    return outDir / (base + ext)

def processImageFile(srcPath: Path, outDir: Path, dpi=DEFAULT_DPI,
    threshold=DEFAULT_THRESHOLD, placement='center', borderRGB=(255, 255, 255),
    outFormat=DEFAULT_OUTPUT_FROMAT, jpegQuality=DEFAULT_JPEG_QUALITY,
    orientation='portrait'):

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
                return {"status": "rejected", "reason": f"scaleX={scaleX:.2f} or scaleY={scaleY:.2f} >= {threshold}", "scaleX": scaleX, "scaleY": scaleY}

            if im.mode not in ("RGB", "RGBA"):
                im = im.convert("RGB")

            canvas, usedScale = fitAndPad(im, targetW, targetH, placement=placement, borderRGB=borderRGB)
            final = convertToCMYK(canvas)
            outPath = chooseOutputName(srcPath, outDir, fmt=outFormat)

            saveKwargs = {"dpi": (dpi, dpi)}
            if outFormat.upper() == "JPEG":
                saveKwargs["quality"] = jpegQuality
                final = final.convert("RGB")
                final.save(outPath, "JPEG", **saveKwargs)
            else:
                final.save(outPath, "TIFF", compression="tiff_lzw", **saveKwargs)

            return {"status": "converted", "outPath": str(outPath), "scaleX": scaleX, "scaleY": scaleY}
    except Exception as e:
        return {"status": "error", "reason": str(e)}