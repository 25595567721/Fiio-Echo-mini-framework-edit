#!/usr/bin/env python3
"""
替换开机Logo（等长覆盖）
交互式运行：python replace_logo.py
命令行运行：python replace_logo.py [固件] [logo.png] [起始帧] [结束帧]
"""
from PIL import Image
import sys
import os
import shutil

BASE = 0x9BCD12
FRAME_START_ABS = BASE + 0x6930  # Z_POWERON0 像素绝对偏移
FRAME_SIZE = 0x1A900              # 108,800 bytes per frame
W, H = 320, 170


def png_to_rgb565(png_path, w=W, h=H):
    """PNG → RGB565 字节流"""
    img = Image.open(png_path).convert("RGB")
    if img.size != (w, h):
        print(f"图片尺寸 {img.size} ≠ ({w},{h})，自动缩放...")
        img = img.resize((w, h), Image.LANCZOS)
    raw = img.tobytes()  # RGB888
    out = bytearray(w * h * 2)
    for p in range(w * h):
        r = raw[p*3] >> 3
        g = raw[p*3+1] >> 2
        b = raw[p*3+2] >> 3
        out[p*2]   = (r << 3) | (g >> 3)
        out[p*2+1] = ((g & 0x07) << 5) | b
    return bytes(out)


def ask(prompt, default=None, validator=None):
    """交互式提问，支持默认值和校验"""
    while True:
        suffix = f" [{default}]" if default is not None else ""
        ans = input(f"{prompt}{suffix}: ").strip()
        if not ans and default is not None:
            ans = str(default)
        if validator is None or validator(ans):
            return ans
        print("  ✗ 输入无效，请重试")


def valid_file(path):
    """校验文件存在"""
    return os.path.isfile(path)


def valid_frame(s):
    """校验帧号范围 0-39"""
    try:
        return 0 <= int(s) <= 39
    except ValueError:
        return False


if __name__ == "__main__":
    # ---------- 1. 询问固件文件名 ----------
    if len(sys.argv) >= 2:
        img_path = sys.argv[1]
    else:
        img_path = ask("固件镜像文件名", default="HIFIEC39.IMG",
                       validator=valid_file)
    if not os.path.isfile(img_path):
        print(f"错误：固件文件不存在 {img_path}")
        sys.exit(1)

    file_size = os.path.getsize(img_path)
    print(f"  ✓ 固件: {img_path} ({file_size/1024/1024:.1f} MB)")
    # 简单完整性检查：文件应该足够大
    need_size = FRAME_START_ABS + 40 * FRAME_SIZE
    if file_size < need_size:
        print(f"错误：文件太小，至少需要 {need_size} 字节，实际 {file_size}")
        sys.exit(1)

    # ---------- 2. 询问 Logo 图片 ----------
    if len(sys.argv) >= 3:
        png_path = sys.argv[2]
    else:
        png_path = ask("Logo 图片文件名", validator=valid_file)
    if not os.path.isfile(png_path):
        print(f"错误：图片文件不存在 {png_path}")
        sys.exit(1)

    # ---------- 3. 询问帧范围 ----------
    if len(sys.argv) >= 5:
        start_f, end_f = int(sys.argv[3]), int(sys.argv[4])
    else:
        start_f = int(ask("替换起始帧 (Logo渐显建议从2开始)", default=2,
                          validator=valid_frame))
        end_f = int(ask("替换结束帧 (建议6)", default=6,
                        validator=valid_frame))
    if start_f > end_f:
        start_f, end_f = end_f, start_f

    # ---------- 4. 转换图片 ----------
    print(f"\n处理中：{img_path} ← {png_path}  帧 {start_f}~{end_f}")
    logo_data = png_to_rgb565(png_path)
    if len(logo_data) != W * H * 2:
        print(f"错误：转换后字节数 {len(logo_data)} ≠ {W*H*2}")
        sys.exit(1)

    # ---------- 5. 备份 ----------
    backup_path = img_path + ".backup"
    if os.path.exists(backup_path):
        print(f"备份文件已存在，跳过备份: {backup_path}")
    else:
        shutil.copy2(img_path, backup_path)
        print(f"已备份 → {backup_path}")

    # ---------- 6. 写入 ----------
    with open(img_path, "r+b") as f:
        for frame in range(start_f, end_f + 1):
            off = FRAME_START_ABS + frame * FRAME_SIZE
            f.seek(off)
            f.write(logo_data)
            print(f"  帧 {frame:02d}: 写入偏移 0x{off:x}")

    print(f"\n✅ 完成！已替换帧 {start_f}~{end_f}")
    print("   现在可以刷入设备测试")

