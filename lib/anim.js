// Size and length of a GIF or (animated) WebP, read from the file itself, so the upload caps hold even when ffmpeg is
// missing, and for animated WebP, which ffmpeg cannot decode. Returns { width, height, seconds, frames } or null when
// the bytes can't be read.
'use strict';

/** GIF: logical screen size, and the frame delays from each Graphic Control Extension. */
function gifInfo(buf) {
  if (buf.length < 13) return null;
  const width = buf.readUInt16LE(6), height = buf.readUInt16LE(8), packed = buf[10];
  let p = 13 + (packed & 0x80 ? 3 * (2 << (packed & 7)) : 0);
  let frames = 0, centis = 0, delay = 0;
  const skipSubBlocks = () => { while (p < buf.length && buf[p] !== 0) p += buf[p] + 1; p++; };
  while (p < buf.length) {
    const b = buf[p++];
    if (b === 0x3b) break; // trailer
    if (b === 0x21) { // extension
      const label = buf[p++];
      if (label === 0xf9 && buf[p] >= 4 && p + 4 < buf.length) delay = buf.readUInt16LE(p + 2);
      skipSubBlocks();
    } else if (b === 0x2c) { // image
      if (p + 9 > buf.length) break;
      const lp = buf[p + 8];
      p += 9 + (lp & 0x80 ? 3 * (2 << (lp & 7)) : 0) + 1; // descriptor, local colour table, LZW code size
      skipSubBlocks();
      frames++;
      centis += delay <= 1 ? 10 : delay; // browsers play 0 and 1 as 10/100 s
      delay = 0;
    } else break; // corrupt: keep what was read
  }
  return frames ? { width, height, seconds: frames > 1 ? centis / 100 : 0, frames } : null;
}

/** WebP: canvas size from VP8X (or the single VP8 / VP8L frame), and the ANMF frame durations. */
function webpInfo(buf) {
  if (buf.length < 30) return null;
  const u24 = o => buf[o] | buf[o + 1] << 8 | buf[o + 2] << 16;
  let width = 0, height = 0, frames = 0, ms = 0;
  for (let p = 12; p + 8 <= buf.length;) {
    const id = buf.toString('latin1', p, p + 4), size = buf.readUInt32LE(p + 4), d = p + 8;
    if (id === 'VP8X' && d + 10 <= buf.length) { width = u24(d + 4) + 1; height = u24(d + 7) + 1; }
    else if (id === 'ANMF' && d + 16 <= buf.length) { frames++; ms += u24(d + 12); }
    else if (id === 'VP8 ' && !width && d + 10 <= buf.length) { width = buf.readUInt16LE(d + 6) & 0x3fff; height = buf.readUInt16LE(d + 8) & 0x3fff; frames = 1; }
    else if (id === 'VP8L' && !width && d + 5 <= buf.length) { const v = buf.readUInt32LE(d + 1); width = (v & 0x3fff) + 1; height = (v >> 14 & 0x3fff) + 1; frames = 1; }
    p = d + size + (size & 1);
  }
  return width && frames ? { width, height, seconds: ms / 1000, frames } : null;
}

module.exports = { gifInfo, webpInfo };
