/**
 * Client-side image normalization for uploads.
 *
 * Phones produce photos the backend chokes on or handles slowly: HEIC from
 * iPhones, 48MP/20MB files, EXIF-rotated JPEGs. Normalizing in the browser
 * fixes all three at once — decode whatever this device can produce (Safari
 * decodes HEIC natively), bake the EXIF orientation into pixels, downscale
 * to a sane size, and re-encode as JPEG that every backend path accepts.
 *
 * If the browser can't decode the file (e.g. HEIC dragged into Chrome on
 * Windows), the original file is returned and the backend takes its chance.
 */

const MAX_DIMENSION = 2000;
const JPEG_QUALITY = 0.9;

async function decodeToBitmap(file: File): Promise<ImageBitmap | HTMLImageElement> {
  try {
    // imageOrientation:"from-image" bakes EXIF rotation (default in modern
    // browsers, explicit for older Safari)
    return await createImageBitmap(file, { imageOrientation: "from-image" });
  } catch {
    // Fallback decoder: <img> also applies EXIF orientation on decode
    const url = URL.createObjectURL(file);
    try {
      const img = new Image();
      img.decoding = "async";
      img.src = url;
      await img.decode();
      return img;
    } finally {
      URL.revokeObjectURL(url);
    }
  }
}

export async function normalizeImageFile(
  file: File,
  maxDim: number = MAX_DIMENSION,
): Promise<File> {
  // Non-image or tiny file: nothing to gain
  if (!file.type.startsWith("image/") && !/\.(heic|heif)$/i.test(file.name)) {
    return file;
  }

  let source: ImageBitmap | HTMLImageElement;
  try {
    source = await decodeToBitmap(file);
  } catch {
    return file; // undecodable here — let the backend try
  }

  const width = "naturalWidth" in source ? source.naturalWidth : source.width;
  const height = "naturalHeight" in source ? source.naturalHeight : source.height;
  if (!width || !height) return file;

  const scale = Math.min(1, maxDim / Math.max(width, height));
  const outW = Math.max(1, Math.round(width * scale));
  const outH = Math.max(1, Math.round(height * scale));

  // Already a small, safe JPEG/PNG/WebP? Skip the re-encode.
  const safeType = ["image/jpeg", "image/png", "image/webp"].includes(file.type);
  if (safeType && scale === 1 && file.size < 4 * 1024 * 1024) {
    if ("close" in source) source.close();
    return file;
  }

  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.drawImage(source, 0, 0, outW, outH);
  if ("close" in source) source.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  if (!blob) return file;

  const newName = file.name.replace(/\.[^.]+$/, "") + ".jpg";
  return new File([blob], newName, { type: "image/jpeg" });
}
