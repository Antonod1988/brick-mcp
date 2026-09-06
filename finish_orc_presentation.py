"""Deliver the clean assembly video and preserve the existing English-captioned cut."""

import gzip
import json
import subprocess
import shutil
import zipfile
from pathlib import Path
from PIL import Image, ImageOps, ImageStat

ROOT = Path(__file__).parent
OUT = ROOT / "output/orc-kraken-ship/presentation"
POST = OUT / "for-post"
FF = Path(
    r"C:\Users\user\AppData\Local\Programs\Python\Python311\Lib\site-packages\imageio_ffmpeg\binaries\ffmpeg-win-x86_64-v7.1.exe"
)


def main():
    POST.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "model.json.gz", "rt", encoding="utf8") as f:
        data = json.load(f)
    total = len(data["stages"])
    raw = OUT / "build-frames"
    images = sorted((OUT / "renders").glob("*.png"))
    assert len(images) == 8
    for source in images:
        im = Image.open(source).convert("RGB")
        assert max(ImageStat.Stat(im).mean) > 12, source
        im.save(POST / (source.stem + ".jpg"), quality=95, subsampling=0)
    for index in range(1, total + 1):
        file = raw / f"{index:04d}.png"
        im = Image.open(file).convert("RGB")
        assert im.size == (1080, 1080) and max(ImageStat.Stat(im).mean) > 10, file
    frames = (
        [(raw / "0001.png", 0.5)]
        + [(raw / f"{i:04d}.png", 0.125) for i in range(1, total + 1)]
        + [(raw / f"{total:04d}.png", 3.5)]
    )
    duration = sum(t for _, t in frames)
    lines = []
    for file, t in frames:
        lines += [f"file '{file.as_posix()}'", f"duration {t:.6f}"]
    lines += [f"file '{frames[-1][0].as_posix()}'"]
    playlist = OUT / "assembly-only-concat.txt"
    playlist.write_text("\n".join(lines) + "\n", encoding="utf8")
    movie = POST / "orc-kraken-assembly.mp4"
    subprocess.run(
        [
            str(FF),
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(playlist),
            "-vf",
            f"fps=24,fade=t=in:st=0:d=0.25,fade=t=out:st={duration-.45:.3f}:d=0.45",
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "19",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(movie),
        ],
        check=True,
    )
    # Decode the complete deliverable before packaging it.
    subprocess.run(
        [str(FF), "-v", "error", "-i", str(movie), "-f", "null", "-"], check=True
    )
    sheet = Image.new("RGB", (1800, 960), "#101922")
    for i, source in enumerate(images):
        tile = ImageOps.contain(
            Image.open(source).convert("RGB"), (438, 468), Image.Resampling.LANCZOS
        )
        sheet.paste(
            tile,
            (
                (i % 4) * 450 + (450 - tile.width) // 2,
                (i // 4) * 480 + (480 - tile.height) // 2,
            ),
        )
    sheet.save(OUT / "contact-sheet.jpg", quality=93)
    english = OUT / "post-ready/orc-kraken-build-en.mp4"
    extra = []
    if english.exists():
        shutil.copy2(english, POST / english.name)
        extra.append(POST / english.name)
    info = {
        "stills": 8,
        "elements": len(data["parts"]),
        "assembly_steps": total,
        "video_seconds": duration,
        "video_size": [1080, 1080],
        "fps": 24,
        "captions": False,
        "videos": 1 + len(extra),
        "additional_english_version": bool(extra),
    }
    (OUT / "delivery.json").write_text(json.dumps(info, indent=2), encoding="utf8")
    (POST / "README.txt").write_text(
        "Материалы для поста\n\n8 чистых рендеров: семь квадратных 2048×2048 и один широкий 2560×1440.\nОсновное видео: orc-kraken-assembly.mp4 — 22 секунды, только сборка, без текста и дополнительных вставок.\nДополнительное видео: orc-kraken-build-en.mp4 — 25 секунд, английские титры и два крупных плана.\nОба ролика: 1080×1080, 24 кадра/с, H.264, без звука.\n\nПоказаны 147 сохранённых этапов модели из 863 элементов. PNG-мастера и сцена Blender доступны отдельно в исходной папке presentation. Рендер: Blender/Cycles и Eevee, геометрия деталей LDraw из Studio.\n",
        encoding="utf8",
    )
    deliveries = (
        [POST / (p.stem + ".jpg") for p in images]
        + [movie]
        + extra
        + [POST / "README.txt"]
    )
    assert len(deliveries) == 10 + len(extra)
    with zipfile.ZipFile(
        OUT / "Orc-Kraken-presentation.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=5
    ) as z:
        for file in deliveries:
            z.write(file, file.name)
    print("DELIVERY", json.dumps(info), "video_bytes", movie.stat().st_size, flush=True)


if __name__ == "__main__":
    main()
