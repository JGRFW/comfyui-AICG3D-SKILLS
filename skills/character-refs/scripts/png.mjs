// PNG 的最小读写：读尺寸、解像素、写入/读出 iTXt 标识。只用 node 标准库。
//
// 为什么自己写：skill 要零依赖。检查门只需要尺寸和四边像素，标识只需要一个文本块，
// 用不着图像库。只支持 8 位深、非隔行的 PNG——三家出图服务给的都是这种；
// 遇到别的格式就明说「无法检查」，不猜。

import { deflateSync, inflateSync } from 'node:zlib';

const SIG = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

const CRC_TABLE = (() => {
  const t = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    t[n] = c >>> 0;
  }
  return t;
})();

export function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

export const isPng = (buf) => buf.length > 8 && buf.subarray(0, 8).equals(SIG);

/** 逐块遍历：[{type, data, start, end}]，end 是这一块（含 CRC）之后的偏移。 */
export function chunks(buf) {
  if (!isPng(buf)) throw new Error('不是 PNG 文件');
  const out = [];
  let off = 8;
  while (off + 12 <= buf.length) {
    const len = buf.readUInt32BE(off);
    const type = buf.toString('ascii', off + 4, off + 8);
    out.push({ type, data: buf.subarray(off + 8, off + 8 + len), start: off, end: off + 12 + len });
    off += 12 + len;
    if (type === 'IEND') break;
  }
  return out;
}

export function pngInfo(buf) {
  const ihdr = chunks(buf).find((c) => c.type === 'IHDR');
  if (!ihdr) throw new Error('PNG 缺 IHDR');
  const d = ihdr.data;
  return { width: d.readUInt32BE(0), height: d.readUInt32BE(4), depth: d[8], colorType: d[9], interlace: d[12] };
}

function chunk(type, data) {
  const head = Buffer.alloc(8);
  head.writeUInt32BE(data.length, 0);
  head.write(type, 4, 'ascii');
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(Buffer.concat([head.subarray(4), data])), 0);
  return Buffer.concat([head, data, crc]);
}

/**
 * 带透明度的 PNG 铺到白底上，另存成不透明的 RGB（8 位）。
 * GPT（codex）出的图是透明背景：看图软件显示成白底，实际像素是透明的黑，
 * 视频模型拿到怎么处理背景说不准——参考图一律存成实打实的白底。
 * 不带透明度、透明度通道全是不透明、或不是 8 位非隔行（解不开），都原样返回。
 */
export function flattenAlpha(buf) {
  if (!isPng(buf)) return { buf, changed: false };
  const { colorType } = pngInfo(buf);
  if (colorType !== 4 && colorType !== 6) return { buf, changed: false };
  const img = decode(buf);
  if (!img) return { buf, changed: false };
  const { width: w, height: h, bpp, px } = img;
  // 带透明度通道但每个像素都不透明（Qwen 就是）：原样保留，不改文件、不留注
  let anyClear = false;
  for (let i = bpp - 1; i < px.length; i += bpp) if (px[i] < 255) { anyClear = true; break; }
  if (!anyClear) return { buf, changed: false };
  const stride = w * 3;
  const raw = Buffer.alloc(h * (stride + 1));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = (y * w + x) * bpp, o = y * (stride + 1) + 1 + x * 3;
      const a = px[i + bpp - 1] / 255;
      const [r, g, b] = bpp === 2 ? [px[i], px[i], px[i]] : [px[i], px[i + 1], px[i + 2]];
      raw[o] = Math.round(r * a + 255 * (1 - a)); raw[o + 1] = Math.round(g * a + 255 * (1 - a)); raw[o + 2] = Math.round(b * a + 255 * (1 - a));
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return { buf: Buffer.concat([SIG, chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]), changed: true };
}

/**
 * 写入 iTXt（UTF-8 文本块）。标识里有中文角色名，tEXt 只收 Latin-1，所以用 iTXt。
 * 同一个关键字已存在就替换，插在 IEND 之前。
 */
export function withText(buf, entries) {
  const kept = chunks(buf).filter((c) => !(c.type === 'iTXt' && Object.hasOwn(entries, c.data.toString('latin1', 0, c.data.indexOf(0)))));
  const iend = kept.findIndex((c) => c.type === 'IEND');
  const parts = [SIG];
  kept.forEach((c, i) => {
    if (i === iend) {
      for (const [k, v] of Object.entries(entries)) {
        // keyword\0 压缩标志 0、压缩方法 0、语言标签 \0、译名 \0、正文（UTF-8）
        parts.push(chunk('iTXt', Buffer.concat([Buffer.from(k, 'latin1'), Buffer.from([0, 0, 0, 0, 0]), Buffer.from(String(v), 'utf8')])));
      }
    }
    parts.push(buf.subarray(c.start, c.end));
  });
  return Buffer.concat(parts);
}

export function readText(buf) {
  const out = {};
  for (const c of chunks(buf)) {
    if (c.type !== 'iTXt') continue;
    const k = c.data.indexOf(0);
    const key = c.data.toString('latin1', 0, k);
    // 跳过 压缩标志、压缩方法，再跳过语言标签与译名两个以 \0 结尾的串
    let p = k + 3;
    p = c.data.indexOf(0, p) + 1;
    p = c.data.indexOf(0, p) + 1;
    out[key] = c.data.toString('utf8', p);
  }
  return out;
}

/** 解出 RGB(A) 像素。只支持 8 位深、非隔行；否则返回 null（门会明说跳过）。 */
export function decode(buf) {
  const info = pngInfo(buf);
  const bpp = { 0: 1, 2: 3, 4: 2, 6: 4 }[info.colorType];
  if (info.depth !== 8 || !bpp || info.interlace) return null;
  const raw = inflateSync(Buffer.concat(chunks(buf).filter((c) => c.type === 'IDAT').map((c) => c.data)));
  const { width: w, height: h } = info;
  const stride = w * bpp;
  const px = Buffer.alloc(h * stride);
  let prev = Buffer.alloc(stride);
  for (let y = 0; y < h; y++) {
    const f = raw[y * (stride + 1)];
    const line = raw.subarray(y * (stride + 1) + 1, (y + 1) * (stride + 1));
    const out = px.subarray(y * stride, (y + 1) * stride);
    for (let x = 0; x < stride; x++) {
      const a = x >= bpp ? out[x - bpp] : 0;
      const up = prev[x];
      const c = x >= bpp ? prev[x - bpp] : 0;
      const p = a + up - c;
      const pa = Math.abs(p - a), pb = Math.abs(p - up), pc = Math.abs(p - c);
      const pred = [0, a, up, (a + up) >> 1, pa <= pb && pa <= pc ? a : pb <= pc ? up : c][f];
      out[x] = (line[x] + pred) & 255;
    }
    prev = out;
  }
  return { width: w, height: h, bpp, px };
}

/** 生成纯色 RGB PNG——只给自测用，也方便调用方造占位图。 */
export function solidPng(w, h, rgb = [255, 255, 255], paint = null) {
  const stride = w * 3;
  const raw = Buffer.alloc(h * (stride + 1));
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const [r, g, b] = paint ? paint(x, y) : rgb;
      const i = y * (stride + 1) + 1 + x * 3;
      raw[i] = r; raw[i + 1] = g; raw[i + 2] = b;
    }
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(w, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  return Buffer.concat([SIG, chunk('IHDR', ihdr), chunk('IDAT', deflateSync(raw)), chunk('IEND', Buffer.alloc(0))]);
}
