"""生成应用图标。运行：python scripts/generate_icon.py"""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SIZE = 256
image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
draw = ImageDraw.Draw(image)
draw.rounded_rectangle((5, 5, 250, 250), radius=58, fill="#191c22")
draw.rounded_rectangle((13, 13, 242, 242), radius=50, outline="#30353f", width=3)
center = SIZE // 2
# 准星与点击圆点
draw.line((center, 42, center, 92), fill="#f2b35d", width=13)
draw.line((center, 164, center, 214), fill="#f2b35d", width=13)
draw.line((42, center, 92, center), fill="#f2b35d", width=13)
draw.line((164, center, 214, center), fill="#f2b35d", width=13)
draw.ellipse((82, 82, 174, 174), fill="#e05d5d", outline="#f7f8fa", width=7)
draw.ellipse((112, 112, 144, 144), fill="#f7f8fa")
output = ROOT / "assets" / "icon.ico"
output.parent.mkdir(parents=True, exist_ok=True)
image.save(output, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
print(f"已生成 {output}")
