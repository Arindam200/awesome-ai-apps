import crypto from "node:crypto";
import sharp from "sharp";

// Phone photos arrive rotated by EXIF and often 4000+ px wide. Inkling 2 Small reads images
// best between 40 and 4096 px a side; 2048 px keeps pen strokes sharp at a reasonable token cost.
export const MAX_SIDE = 2048;

export type Sketch = { dataUrl: string; width: number; height: number; hash: string; bytes: Buffer };

export async function normaliseSketch(input: Buffer): Promise<Sketch> {
  const img = sharp(input, { failOn: "none" }).rotate().resize({ width: MAX_SIDE, height: MAX_SIDE, fit: "inside", withoutEnlargement: true }).flatten({ background: "#ffffff" });
  const { data, info } = await img.jpeg({ quality: 88 }).toBuffer({ resolveWithObject: true });
  if (Math.min(info.width, info.height) < 40) throw new Error("Image is too small to read (under 40 px on a side).");
  return {
    dataUrl: `data:image/jpeg;base64,${data.toString("base64")}`,
    width: info.width,
    height: info.height,
    hash: crypto.createHash("sha256").update(data).digest("hex").slice(0, 16),
    bytes: data,
  };
}

export function pngDataUrl(png: Buffer): string {
  return `data:image/png;base64,${png.toString("base64")}`;
}
