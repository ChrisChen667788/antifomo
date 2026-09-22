import { execFileSync } from 'node:child_process';
import { mkdirSync, mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import puppeteer from 'puppeteer-core';

const root = resolve(import.meta.dirname, '..');
const svgPath = join(root, 'docs/assets/antifomo-signal-loop.svg');
const outputPath = join(root, 'docs/assets/antifomo-signal-loop.gif');
const chromePath = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const frameDir = mkdtempSync(join(tmpdir(), 'anti-fomo-marketing-'));

const svg = readFileSync(svgPath, 'utf8');
const browser = await puppeteer.launch({ executablePath: chromePath, headless: true, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 760, height: 309, deviceScaleFactor: 1 });
  await page.setContent(`<html><body style="margin:0;background:#f5f8f6">${svg}</body></html>`, { waitUntil: 'load' });
  const frames = 60;
  for (let index = 0; index < frames; index += 1) {
    await page.evaluate((timeMs) => document.querySelector('svg')?.setCurrentTime(timeMs / 1000), index * 100);
    await page.screenshot({ path: join(frameDir, `frame-${String(index).padStart(3, '0')}.png`) });
  }
} finally {
  await browser.close();
}

mkdirSync(join(root, 'docs/assets'), { recursive: true });
execFileSync('ffmpeg', [
  '-y', '-loglevel', 'error', '-framerate', '10', '-i', join(frameDir, 'frame-%03d.png'),
  '-vf', 'fps=10,scale=760:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=sierra2_4a',
  '-loop', '0', outputPath,
]);
rmSync(frameDir, { recursive: true, force: true });
console.log(`wrote ${outputPath}`);
