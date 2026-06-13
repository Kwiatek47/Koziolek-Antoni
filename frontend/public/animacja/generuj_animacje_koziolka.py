#!/usr/bin/env python3
"""Generuje animację GIF koziołka biegnącego w lewo i w prawo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

BASE_DIR = Path(__file__).resolve().parent
SOURCE = BASE_DIR / "ostateczna_animacja_zrodlo.png"
OUTPUT_GIF = BASE_DIR / "koziolek_biega.gif"
OUTPUT_FRAMES_DIR = BASE_DIR / "koziolek_klatki"


def remove_background_flood(img: Image.Image, min_white: int = 240) -> Image.Image:
    """Usuwa tylko białe tło połączone z krawędziami obrazu."""
    from collections import deque

    img = img.convert("RGBA")
    width, height = img.size
    pixels = img.load()
    visited = bytearray(width * height)

    def index(x: int, y: int) -> int:
        return y * width + x

    def is_background(r: int, g: int, b: int, a: int) -> bool:
        return a > 0 and r >= min_white and g >= min_white and b >= min_white

    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if is_background(*pixels[x, y]):
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_background(*pixels[x, y]):
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        pixel_index = index(x, y)
        if visited[pixel_index]:
            continue
        r, g, b, a = pixels[x, y]
        if not is_background(r, g, b, a):
            continue
        visited[pixel_index] = 1
        pixels[x, y] = (255, 255, 255, 0)
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    return img


def fill_internal_holes(img: Image.Image) -> Image.Image:
    """Wypełnia przezroczyste dziury wewnątrz postaci białym kolorem."""
    from collections import deque

    img = img.convert("RGBA")
    width, height = img.size
    pixels = img.load()
    external = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def index(x: int, y: int) -> int:
        return y * width + x

    def is_transparent(x: int, y: int) -> bool:
        return pixels[x, y][3] == 0

    for x in range(width):
        for y in (0, height - 1):
            if is_transparent(x, y):
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if is_transparent(x, y):
                queue.append((x, y))

    while queue:
        x, y = queue.popleft()
        pixel_index = index(x, y)
        if external[pixel_index] or not is_transparent(x, y):
            continue
        external[pixel_index] = 1
        if x > 0:
            queue.append((x - 1, y))
        if x + 1 < width:
            queue.append((x + 1, y))
        if y > 0:
            queue.append((x, y - 1))
        if y + 1 < height:
            queue.append((x, y + 1))

    for y in range(height):
        for x in range(width):
            if is_transparent(x, y) and not external[index(x, y)]:
                pixels[x, y] = (255, 255, 255, 255)

    return img


def prepare_frame(img: Image.Image) -> Image.Image:
    return fill_internal_holes(remove_background_flood(img))


def trim(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def split_sprite(sheet: Image.Image) -> list[Image.Image]:
    width, height = sheet.size
    frame_w, frame_h = width // 2, height // 2
    frames: list[Image.Image] = []
    for row in range(2):
        for col in range(2):
            box = (col * frame_w, row * frame_h, (col + 1) * frame_w, (row + 1) * frame_h)
            frame = trim(prepare_frame(sheet.crop(box)))
            frames.append(frame)
    return frames


def normalize_frames(frames: list[Image.Image], target_height: int = 300) -> list[Image.Image]:
    normalized: list[Image.Image] = []
    for frame in frames:
        ratio = target_height / frame.height
        new_size = (max(1, int(frame.width * ratio)), target_height)
        normalized.append(frame.resize(new_size, Image.Resampling.LANCZOS))
    return normalized


def rgba_to_palette(img: Image.Image) -> Image.Image:
    alpha = img.getchannel("A")
    background = Image.new("RGBA", img.size, (255, 255, 255, 0))
    rgb = Image.alpha_composite(background, img).convert("RGB")
    palette_img = rgb.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    mask = alpha.point(lambda value: 255 if value < 128 else 0)
    palette_img.paste(255, mask=mask)
    palette_img.info["transparency"] = 255
    return palette_img


def compose_frame(
    canvas_size: tuple[int, int],
    goat: Image.Image,
    x: int,
) -> Image.Image:
    canvas_w, canvas_h = canvas_size
    canvas = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    y = (canvas_h - goat.height) // 2
    canvas.paste(goat, (x, y), goat)
    return rgba_to_palette(canvas)


def build_animation(
    frames: list[Image.Image],
    canvas_w: int = 1100,
    canvas_h: int = 360,
    steps_per_direction: int = 20,
    frame_duration_ms: int = 70,
) -> list[Image.Image]:
    max_goat_w = max(frame.width for frame in frames)
    travel = canvas_w - max_goat_w
    gif_frames: list[Image.Image] = []

    flipped = [frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for frame in frames]

    for step in range(steps_per_direction + 1):
        x = int(step / steps_per_direction * travel)
        goat = frames[step % len(frames)]
        gif_frames.append(compose_frame((canvas_w, canvas_h), goat, x))

    for step in range(steps_per_direction, -1, -1):
        x = int(step / steps_per_direction * travel)
        goat = flipped[(steps_per_direction - step) % len(flipped)]
        gif_frames.append(compose_frame((canvas_w, canvas_h), goat, x))

    return gif_frames, frame_duration_ms


def main() -> None:
    sheet = Image.open(SOURCE)
    frames = split_sprite(sheet)
    normalized = normalize_frames(frames)

    OUTPUT_FRAMES_DIR.mkdir(exist_ok=True)
    for index, frame in enumerate(normalized, start=1):
        frame.save(OUTPUT_FRAMES_DIR / f"klatka_{index}.png")

    gif_frames, duration = build_animation(normalized)
    gif_frames[0].save(
        OUTPUT_GIF,
        save_all=True,
        append_images=gif_frames[1:],
        duration=duration,
        loop=0,
        disposal=2,
        optimize=False,
    )

    print(f"Zapisano {len(normalized)} klatek w: {OUTPUT_FRAMES_DIR}")
    print(f"Zapisano animację GIF ({len(gif_frames)} klatek) w: {OUTPUT_GIF}")


if __name__ == "__main__":
    main()
