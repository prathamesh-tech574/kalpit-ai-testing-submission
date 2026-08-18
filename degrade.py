"""
Creates degraded versions of each original page image, simulating realistic
scan/photograph quality issues:
  - slight skew/rotation
  - reduced contrast/brightness
  - mild gaussian blur + noise
  - light JPEG compression

Each degradation is saved separately AND a combined "all degradations"
version is saved, since real-world scans/photos usually exhibit more than
one issue simultaneously.
"""
import cv2
import numpy as np
import os

SRC_DIR = "original_images"
OUT_DIR = "degraded_images"
os.makedirs(OUT_DIR, exist_ok=True)

def rotate(img, angle):
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), borderValue=(255, 255, 255))

def reduce_contrast_brightness(img, alpha=0.7, beta=-15):
    # alpha < 1 reduces contrast, negative beta darkens slightly
    return cv2.convertScaleAbs(img, alpha=alpha, beta=beta)

def add_blur_noise(img, ksize=3, noise_sigma=8):
    blurred = cv2.GaussianBlur(img, (ksize, ksize), 0)
    noise = np.random.normal(0, noise_sigma, blurred.shape).astype(np.float32)
    noisy = np.clip(blurred.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    return noisy

def jpeg_compress(img, quality=35):
    ok, enc = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return cv2.imdecode(enc, cv2.IMREAD_COLOR)

def process(path):
    name = os.path.splitext(os.path.basename(path))[0]
    img = cv2.imread(path)

    # Combined realistic degradation: rotate -> contrast/brightness -> blur/noise -> jpeg
    degraded = rotate(img, angle=2.5)
    degraded = reduce_contrast_brightness(degraded, alpha=0.72, beta=-18)
    degraded = add_blur_noise(degraded, ksize=3, noise_sigma=10)
    degraded = jpeg_compress(degraded, quality=32)

    out_path = os.path.join(OUT_DIR, f"{name}_degraded.png")
    cv2.imwrite(out_path, degraded)
    print(f"{name}: original {img.shape} -> degraded saved to {out_path}")

if __name__ == "__main__":
    for f in sorted(os.listdir(SRC_DIR)):
        if f.endswith(".png"):
            process(os.path.join(SRC_DIR, f))
