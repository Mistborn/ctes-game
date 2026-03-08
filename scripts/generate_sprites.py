# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "google-genai>=0.8.0",
#   "Pillow>=10.0.0",
# ]
# ///
"""
Generate hex tile sprite PNGs for the world map using Google Imagen.

Usage:
  GOOGLE_API_KEY=xxx uv run scripts/generate_sprites.py
  uv run scripts/generate_sprites.py --api-key KEY
  uv run scripts/generate_sprites.py --terrain plains forest
  uv run scripts/generate_sprites.py --prompts-file custom_prompts.json
  uv run scripts/generate_sprites.py --prompts-json '{"plains": "my prompt"}'
  uv run scripts/generate_sprites.py --overwrite

Output: assets/tiles/{terrain}.png  (120x104px, RGBA, hex-shaped alpha mask)
"""

import argparse
import base64
import io
import json
import math
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw
from google import genai
from google.genai import types


# ---------------------------------------------------------------------------
# Constants — must match game/core/config.py HEX_SIZE = 60
# ---------------------------------------------------------------------------
HEX_W = 120   # 2 * HEX_SIZE
HEX_H = 104   # ceil(sqrt(3) * HEX_SIZE) = ceil(103.92)
CX    = 60    # sprite center x
CY    = 52    # sprite center y
R     = 60    # hex circumradius (same as HEX_SIZE)

ASSETS_DIR = Path(__file__).parent.parent / "assets" / "tiles"

ALL_TERRAINS = ("plains", "forest", "hills", "mountains", "swamp", "ruins", "colony")

# ---------------------------------------------------------------------------
# Default prompts — one per terrain type
# ---------------------------------------------------------------------------
DEFAULT_TERRAIN_PROMPTS: dict[str, str] = {
    "plains": (
        "Top-down aerial view of lush green meadow with wildflowers and short grass, "
        "rolling farmland, soft morning light, fantasy map tile art style, "
        "vivid saturated colors, no people, no text, square crop"
    ),
    "forest": (
        "Top-down aerial view of dense dark-green pine and oak forest canopy, "
        "deep shadows between treetops, ancient woodland, fantasy map tile art style, "
        "rich deep greens, no text, square crop"
    ),
    "hills": (
        "Top-down aerial view of rolling brown and tan hills with rocky outcroppings, "
        "sparse dry grass, warm earthy tones, fantasy map tile art style, "
        "no text, square crop"
    ),
    "mountains": (
        "Top-down aerial view of jagged grey mountain peaks with snow caps, "
        "dramatic rocky terrain, silver and slate blue tones, fantasy map tile art style, "
        "no text, square crop"
    ),
    "swamp": (
        "Top-down aerial view of murky swamp with dark water, moss-covered trees, "
        "lily pads, muddy banks, dark teal and olive green tones, eerie atmosphere, "
        "fantasy map tile art style, no text, square crop"
    ),
    "ruins": (
        "Top-down aerial view of ancient stone ruins overgrown with vines, "
        "crumbling walls and columns, weathered brown and grey stones, "
        "mysterious atmosphere, fantasy map tile art style, no text, square crop"
    ),
    "colony": (
        "Top-down aerial view of a small medieval settlement, thatched roof cottages, "
        "cobblestone paths, town square with market stalls, warm golden tones, "
        "fantasy map tile art style, no text, square crop"
    ),
}


# ---------------------------------------------------------------------------
# Hex mask
# ---------------------------------------------------------------------------
def make_hex_mask() -> Image.Image:
    """RGBA image: white inside the flat-top hex polygon, transparent outside."""
    mask = Image.new("RGBA", (HEX_W, HEX_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(mask)
    vertices = [
        (CX + R * math.cos(math.radians(60 * i)),
         CY + R * math.sin(math.radians(60 * i)))
        for i in range(6)
    ]
    draw.polygon(vertices, fill=(255, 255, 255, 255))
    return mask


# ---------------------------------------------------------------------------
# Image generation + processing
# ---------------------------------------------------------------------------
def generate_image(client: genai.Client, prompt: str, raw_dir: Optional[Path], terrain: str) -> bytes:
    response = client.models.generate_content(
        model="gemini-3.1-flash-image-preview",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
        ),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            data = part.inline_data.data
            # SDK may return raw bytes or a base64 string depending on version
            if isinstance(data, str):
                raw = base64.b64decode(data)
            else:
                raw = data
            if raw_dir is not None:
                raw_dir.mkdir(parents=True, exist_ok=True)
                mime = getattr(part.inline_data, "mime_type", "image/png")
                ext = mime.split("/")[-1] if mime else "bin"
                raw_path = raw_dir / f"{terrain}.{ext}"
                raw_path.write_bytes(raw)
                print(f"    Raw saved: {raw_path}")
            return raw
    raise RuntimeError("No image in response")


def process_image(raw_bytes: bytes, mask: Image.Image) -> Image.Image:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    img = img.resize((HEX_W, HEX_H), Image.LANCZOS)
    img.putalpha(mask.split()[3])  # apply hex-shaped alpha channel
    return img


def save_sprite(img: Image.Image, terrain: str) -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ASSETS_DIR / f"{terrain}.png"
    img.save(out_path, "PNG")
    print(f"  Saved {out_path}")


# ---------------------------------------------------------------------------
# Argument parsing + prompt loading
# ---------------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate hex tile sprites via Google Imagen"
    )
    p.add_argument(
        "--api-key",
        default=os.environ.get("GOOGLE_API_KEY"),
        help="Google AI Studio API key (default: $GOOGLE_API_KEY)",
    )
    p.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenerate even if the output file already exists",
    )
    p.add_argument(
        "--terrain",
        nargs="*",
        metavar="TERRAIN",
        help=f"Specific terrains to generate (default: all). Choices: {', '.join(ALL_TERRAINS)}",
    )
    p.add_argument(
        "--prompts-file",
        metavar="FILE",
        help="JSON file mapping terrain name -> prompt string. Missing terrains use defaults.",
    )
    p.add_argument(
        "--prompts-json",
        metavar="JSON",
        help="Inline JSON mapping terrain name -> prompt string (alternative to --prompts-file).",
    )
    p.add_argument(
        "--raw-dir",
        metavar="DIR",
        default="assets/tiles/raw",
        help="Directory to save raw images from Gemini before hex-masking (default: assets/tiles/raw).",
    )
    return p.parse_args()


def load_custom_prompts(args: argparse.Namespace) -> dict[str, str]:
    if args.prompts_file:
        return json.loads(Path(args.prompts_file).read_text(encoding="utf-8"))
    if args.prompts_json:
        return json.loads(args.prompts_json)
    return {}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    args = parse_args()

    if not args.api_key:
        sys.exit("Error: provide a Google API key via $GOOGLE_API_KEY or --api-key")

    terrains: tuple[str, ...] = tuple(args.terrain) if args.terrain else ALL_TERRAINS
    unknown = set(terrains) - set(ALL_TERRAINS)
    if unknown:
        sys.exit(f"Error: unknown terrain(s): {', '.join(sorted(unknown))}. "
                 f"Valid choices: {', '.join(ALL_TERRAINS)}")

    custom = load_custom_prompts(args)
    prompts = {t: custom.get(t, DEFAULT_TERRAIN_PROMPTS[t]) for t in terrains}

    client = genai.Client(api_key=args.api_key)
    mask = make_hex_mask()

    for terrain in terrains:
        out_path = ASSETS_DIR / f"{terrain}.png"
        if out_path.exists() and not args.overwrite:
            print(f"  Skipping {terrain} (exists; use --overwrite to replace)")
            continue

        print(f"  Generating {terrain}...")
        print(f"    Prompt: {prompts[terrain][:80]}{'...' if len(prompts[terrain]) > 80 else ''}")
        raw_dir = Path(args.raw_dir) if args.raw_dir else None
        try:
            raw = generate_image(client, prompts[terrain], raw_dir, terrain)
            img = process_image(raw, mask)
            save_sprite(img, terrain)
        except Exception as e:
            print(f"  ERROR generating {terrain}: {e}", file=sys.stderr)

    print("Done.")


if __name__ == "__main__":
    main()
