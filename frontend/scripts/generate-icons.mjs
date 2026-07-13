// Genera los íconos PWA/favicon y el logo chico del header a partir de
// public/logo.png (la llama de Spitwise). Uso: node scripts/generate-icons.mjs
import path from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const pub = (f) => path.join(root, "public", f);

const CANVAS = "#F7F5F1";
const src = pub("logo.png");

// mascot ocupa `scale` del lado del ícono, centrada sobre fondo crema
async function icon(size, scale, out) {
  const inner = Math.round(size * scale);
  const mascot = await sharp(src).resize(inner, inner).png().toBuffer();
  await sharp({
    create: { width: size, height: size, channels: 4, background: CANVAS },
  })
    .composite([{ input: mascot, gravity: "centre" }])
    .png()
    .toFile(pub(out));
  console.log("✓", out);
}

await icon(192, 0.88, "icon-192.png");
await icon(512, 0.88, "icon-512.png");
// maskable: la zona segura es el 80% central → mascota más chica
await icon(192, 0.62, "icon-maskable-192.png");
await icon(512, 0.62, "icon-maskable-512.png");
await icon(180, 0.82, "apple-touch-icon.png");

// Logo chico para headers (transparente, liviano; el original pesa ~700 KB).
await sharp(src).resize(144, 144).png({ compressionLevel: 9 }).toFile(pub("logo-sm.png"));
console.log("✓ logo-sm.png");
