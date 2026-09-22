import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const project = join(root, "videos/anti-fomo-promo");
const outputDir = join(root, "docs/assets/marketing");
const tempDir = mkdtempSync(join(tmpdir(), "anti-fomo-overview-"));
const ffmpeg = process.env.FFMPEG_PATH || "ffmpeg";
const ffprobe = process.env.FFPROBE_PATH || "ffprobe";
const hyperframesVersion = "0.8.60";
const sourceManifestPath = "docs/assets/screenshots/screenshot-manifest.json";
const sourceManifest = JSON.parse(
  readFileSync(join(root, sourceManifestPath), "utf8"),
);
const scenes = JSON.parse(readFileSync(join(project, "scenes.json"), "utf8"));
const digest = (path) =>
  createHash("sha256").update(readFileSync(path)).digest("hex");
const run = (command, args, options = {}) =>
  execFileSync(command, args, { stdio: "inherit", ...options });
const inspect = (path) =>
  JSON.parse(
    execFileSync(
      ffprobe,
      [
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_name,width,height,nb_frames,avg_frame_rate",
        "-of",
        "json",
        path,
      ],
      { encoding: "utf8" },
    ),
  );

try {
  for (const scene of scenes) {
    const source = join(root, "docs/assets/screenshots", scene.source);
    const adopted = join(project, "assets", scene.source);
    if (!existsSync(adopted) || digest(source) !== digest(adopted)) {
      throw new Error(
        `Adopted screenshot differs from repository source: ${scene.source}`,
      );
    }
  }
  run("npx", ["--yes", `hyperframes@${hyperframesVersion}`, "check"], {
    cwd: project,
  });
  const mp4Path = join(tempDir, "antifomo-overview.mp4");
  run(
    "npx",
    [
      "--yes",
      `hyperframes@${hyperframesVersion}`,
      "render",
      "--fps",
      "30",
      "--quality",
      "looks",
      "--output",
      mp4Path,
    ],
    { cwd: project },
  );
  const gifPath = join(tempDir, "antifomo-overview.gif");
  run(ffmpeg, [
    "-y",
    "-loglevel",
    "error",
    "-i",
    mp4Path,
    "-vf",
    "fps=8,scale=760:-2:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128:stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle",
    "-loop",
    "0",
    gifPath,
  ]);
  const posterPath = join(tempDir, "poster.png");
  run(ffmpeg, [
    "-y",
    "-loglevel",
    "error",
    "-ss",
    "1.5",
    "-i",
    mp4Path,
    "-frames:v",
    "1",
    posterPath,
  ]);
  const socialCardPath = join(tempDir, "social-card.png");
  run(ffmpeg, [
    "-y",
    "-loglevel",
    "error",
    "-i",
    posterPath,
    "-vf",
    "scale=1120:630:flags=lanczos,pad=1200:630:40:0:color=0xf1f4ef",
    "-frames:v",
    "1",
    socialCardPath,
  ]);
  const contactSheetPath = join(tempDir, "contact-sheet.jpg");
  run(ffmpeg, [
    "-y",
    "-loglevel",
    "error",
    "-i",
    mp4Path,
    "-vf",
    "select='eq(n,45)+eq(n,135)+eq(n,225)+eq(n,315)+eq(n,405)+eq(n,435)',scale=640:360:flags=lanczos,tile=3x2",
    "-frames:v",
    "1",
    "-q:v",
    "3",
    contactSheetPath,
  ]);
  const video = inspect(mp4Path);
  if (Math.abs(Number(video.format.duration) - 15) > 0.05)
    throw new Error("Overview duration must be 15 seconds");
  if (statSync(gifPath).size > 6 * 1024 * 1024)
    throw new Error("Overview GIF exceeds the 6 MiB asset budget");
  if (statSync(mp4Path).size > 20 * 1024 * 1024)
    throw new Error("Overview MP4 exceeds the 20 MiB asset budget");
  mkdirSync(outputDir, { recursive: true });
  const outputPaths = [
    mp4Path,
    gifPath,
    posterPath,
    socialCardPath,
    contactSheetPath,
  ];
  for (const path of outputPaths)
    copyFileSync(path, join(outputDir, path.split("/").at(-1)));
  // Wall-clock time belongs in build provenance, never in the composition timeline.
  const generatedAt = new Date().toISOString();
  const sourceFiles = [
    "index.html",
    "scenes.json",
    "frame.md",
    "hyperframes.json",
    "package.json",
    "BRIEF.md",
    "STORYBOARD.md",
    "SCRIPT.md",
    ...readdirSync(join(project, "compositions"))
      .filter((path) => path.endsWith(".html"))
      .map((path) => `compositions/${path}`),
  ];
  const manifest = {
    schema_version: "anti-fomo-marketing-overview/v2",
    generated_at: generatedAt,
    renderer: {
      framework: "HyperFrames",
      version: hyperframesVersion,
      composition: "videos/anti-fomo-promo/index.html",
      fps: 30,
    },
    source_mode: "historical_demo_screenshot_montage",
    source_manifest: {
      path: sourceManifestPath,
      sha256: digest(join(root, sourceManifestPath)),
      version: sourceManifest.version,
      release_tag: sourceManifest.release_tag,
      generated_at: sourceManifest.generated_at,
    },
    source_screenshots: scenes.map((scene) => ({
      path: `docs/assets/screenshots/${scene.source}`,
      sha256: digest(join(project, "assets", scene.source)),
    })),
    composition_sources: sourceFiles.map((path) => ({
      path: `videos/anti-fomo-promo/${path}`,
      sha256: digest(join(project, path)),
    })),
    render_script: {
      path: "scripts/render_antifomo_marketing_overview.mjs",
      sha256: digest(fileURLToPath(import.meta.url)),
    },
    bundled_dependencies: [
      "assets/gsap.min.js",
      ...readdirSync(join(project, "assets/fonts")).map(
        (path) => `assets/fonts/${path}`,
      ),
    ].map((path) => ({
      path: `videos/anti-fomo-promo/${path}`,
      sha256: digest(join(project, path)),
    })),
    audio: "deliberate_silence",
    live_workflow_recording: false,
    physical_device_capture: false,
    current_ui_claim: false,
    production_claim: false,
    release_approval_evidence: false,
    assets: outputPaths.map((path) => ({
      path: `docs/assets/marketing/${path.split("/").at(-1)}`,
      sha256: digest(path),
      size_bytes: statSync(path).size,
      probe: inspect(path),
    })),
  };
  writeFileSync(
    join(outputDir, "manifest.json"),
    `${JSON.stringify(manifest, null, 2)}\n`,
  );
  console.log(
    `Wrote 15-second HyperFrames overview and derivatives to ${relative(root, outputDir)}`,
  );
} finally {
  rmSync(tempDir, { recursive: true, force: true });
}
