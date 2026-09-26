// Evidence-image encoder: 50% scale, WebP quality 70. Tall pages are split into tiles of at most
// TILE_HEIGHT px (after scaling) so each committed image stays under the 300 KB evidence limit without
// lowering quality. Output: <stem>.webp, or <stem>-1.webp, <stem>-2.webp, ... when tiled.
// CLI: node scripts/webp.mjs <dir>   (converts every <name>.png in <dir>)
import { readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

export const WEBP_QUALITY = 70;
export const WEBP_SCALE = 0.5;
export const TILE_HEIGHT = 4000;

export async function toWebp(pngPath, webpPath) {
  const { width = 780, height = 1688 } = await sharp(pngPath, { limitInputPixels: false }).metadata();
  const w = Math.round(width * WEBP_SCALE);
  const h = Math.round(height * WEBP_SCALE);
  const scaled = await sharp(pngPath, { limitInputPixels: false }).resize({ width: w }).png().toBuffer();
  const tiles = Math.ceil(h / TILE_HEIGHT);
  const outputs = [];
  for (let i = 0; i < tiles; i++) {
    const top = i * TILE_HEIGHT;
    const out = tiles === 1 ? webpPath : webpPath.replace(/\.webp$/, `-${i + 1}.webp`);
    await sharp(scaled, { limitInputPixels: false })
      .extract({ left: 0, top, width: w, height: Math.min(TILE_HEIGHT, h - top) })
      .webp({ quality: WEBP_QUALITY })
      .toFile(out);
    outputs.push(out);
  }
  return outputs;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const dir = process.argv[2];
  for (const f of readdirSync(dir).filter((n) => n.endsWith(".png"))) {
    const outs = await toWebp(join(dir, f), join(dir, f.replace(/\.png$/, ".webp")));
    console.log(`webp: ${f} -> ${outs.map((o) => o.slice(dirname(o).length + 1)).join(", ")}`);
  }
}
