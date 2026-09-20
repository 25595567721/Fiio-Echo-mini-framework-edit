#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme_replace.py — Echo Mini 固件资源替换工具（统一版）
========================================================

【模式一：开机帧替换】完全兼容 replace_startup.py 的全部用法
  python3 theme_replace.py <固件> <图片> <起始帧> <结束帧>
  python3 theme_replace.py                        # 无参数进入交互式
  原 replace_startup.py / 各 shell 脚本的调用方式原样可用：
    python3 theme_replace.py echo.img logo.png 2 6
    python3 theme_replace.py echo.img png/01.png 0 0

  帧号与资源条目对应关系（连续排列，每帧 0x1A900 字节）：
    帧 0      = #0  POWERON0   ← 开机前导帧，必须是纯黑！
    帧 1      = #1  POWERON1   ← 同上，必须是纯黑！
    帧 2~41   = #2~#41 Z_POWERON0~39（40帧开机动画）
  ※ 关机画面不在此范围，用主题模式 "#42" 替换

【模式二：主题资源替换】需要先用 theme_extract.py 生成 theme_dump/manifest.json
  python3 theme_replace.py <固件> <名称> <png>          # 精确名，所有匹配项
  python3 theme_replace.py <固件> A:<名称> <png>        # 限定主题 A/B/C/D/E/G
  python3 theme_replace.py <固件> ALL:<名称> <png>      # 5套主题全部
  python3 theme_replace.py <固件> <前缀>* <png>         # 前缀通配
  python3 theme_replace.py <固件> #<序号> <png>         # 按条目序号（最可靠）
  示例：
    python3 theme_replace.py echo.img A:MUSIC_BACKGROUND bg.png
    python3 theme_replace.py echo.img "#42" shutdown.png   # 关机画面
"""
import json
import os
import re
import shutil
import sys
from PIL import Image

# ==================== 固件常量（Echo Mini V3.9.0 / HIFIEC39.IMG）====================
RES_BASE      = 0x9BCD12          # ROCK26IMAGERES 容器起始
FRAME0_OFF    = 0x6930            # 条目 #0 (POWERON0) 数据偏移（相对 RES_BASE）
FRAME_SIZE    = 0x1A900           # 每帧 108,800 字节 = 320*170*2
W, H          = 320, 170
FRAME_MIN     = 0
FRAME_MAX     = 41                # 0=POWERON0, 1=POWERON1, 2~41=Z_POWERON0~39
BLACK_FRAMES  = (0, 1)            # 必须为纯黑的前导帧
MANIFEST      = os.path.join("theme_dump", "manifest.json")

_PAT_FULL = re.compile(r"_\([\d\s.,]*\)\.BMP$", re.I)
_PAT_BMP  = re.compile(r"\.BMP$", re.I)

def norm(n):
    return _PAT_BMP.sub("", _PAT_FULL.sub("", n)).strip()

# ==================== 图片编码 ====================
def encode_rgb565(img, w, h):
    """PIL Image → RGB565 小端字节流（已验证的格式）"""
    img = img.convert("RGB")
    if img.size != (w, h):
        print(f"  尺寸 {img.size} → ({w},{h})，自动缩放")
        img = img.resize((w, h), Image.LANCZOS)
    try:
        import numpy as np
        a = np.frombuffer(img.tobytes(), dtype=np.uint8).reshape(h, w, 3).astype(np.uint32)
        r, g, b = a[..., 0] >> 3, a[..., 1] >> 2, a[..., 2] >> 3
        out = np.empty((h, w, 2), dtype=np.uint8)
        out[..., 0] = (r << 3) | (g >> 3)
        out[..., 1] = ((g & 7) << 5) | b
        return out.tobytes()
    except ImportError:
        raw = img.tobytes()
        out = bytearray(w * h * 2)
        for p in range(w * h):
            r, g, b = raw[p*3] >> 3, raw[p*3+1] >> 2, raw[p*3+2] >> 3
            out[p*2]   = (r << 3) | (g >> 3)
            out[p*2+1] = ((g & 7) << 5) | b
        return bytes(out)

# ==================== 通用工具 ====================
def make_backup(img_path):
    backup = img_path + ".backup"
    if os.path.exists(backup):
        print(f"备份已存在，跳过: {backup}")
    else:
        shutil.copy2(img_path, backup)
        print(f"已备份 → {backup}")

def check_image_file(img_path):
    if not os.path.isfile(img_path):
        print(f"错误：固件文件不存在 {img_path}")
        sys.exit(1)
    size = os.path.getsize(img_path)
    print(f"  ✓ 固件: {img_path} ({size/1024/1024:.1f} MB)")
    return size

def load_png(png_path):
    if not os.path.isfile(png_path):
        print(f"错误：图片文件不存在 {png_path}")
        sys.exit(1)
    return Image.open(png_path)

def warn_if_not_black(img, frames):
    """帧0/帧1 必须是纯黑（开机前导帧），否则设备可能无法安装/启动"""
    if not any(f in BLACK_FRAMES for f in frames):
        return
    from PIL import ImageStat
    mean = ImageStat.Stat(img.convert("L").resize((32, 17))).mean[0]
    if mean > 8:
        print("  ⚠⚠ 警告：帧 0/帧 1 是开机前导帧，必须为纯黑图片！")
        print(f"     当前图片平均亮度 {mean:.0f}/255，刷入后可能无法安装或启动！")
        print("     （6/14/27 帧版本正常而 40 帧失败的已知原因就是这个）")

def ask(prompt, default=None, validator=None):
    while True:
        suffix = f" [{default}]" if default is not None else ""
        ans = input(f"{prompt}{suffix}: ").strip()
        if not ans and default is not None:
            ans = str(default)
        if validator is None or validator(ans):
            return ans
        print("  ✗ 输入无效，请重试")

def is_int(s):
    try:
        int(s); return True
    except ValueError:
        return False

# ==================== 模式一：开机帧替换 ====================
def frame_mode(img_path, png_path, start_f, end_f):
    if not (FRAME_MIN <= start_f <= FRAME_MAX and FRAME_MIN <= end_f <= FRAME_MAX):
        print(f"错误：帧号必须在 {FRAME_MIN}~{FRAME_MAX} 之间")
        sys.exit(1)
    if start_f > end_f:
        start_f, end_f = end_f, start_f

    file_size = check_image_file(img_path)
    need_size = RES_BASE + FRAME0_OFF + (FRAME_MAX + 1) * FRAME_SIZE
    if file_size < need_size:
        print(f"错误：文件太小，至少需要 {need_size} 字节，实际 {file_size}")
        sys.exit(1)

    print(f"\n处理中：{img_path} ← {png_path}  帧 {start_f}~{end_f}")
    img = load_png(png_path)
    warn_if_not_black(img, range(start_f, end_f + 1))
    blob = encode_rgb565(img, W, H)
    assert len(blob) == FRAME_SIZE

    # 若 manifest 存在，交叉验证帧号偏移（静默跳过任何异常）
    try:
        m = json.load(open(MANIFEST))
        for fr in (start_f, end_f):
            e = m[fr]
            expect = FRAME0_OFF + fr * FRAME_SIZE
            if e["offset"] != expect:
                print(f"  ⚠ manifest 中条目 #{fr} ({e['name']}) 偏移 0x{e['offset']:x}"
                      f" ≠ 预期 0x{expect:x}，固件布局可能不同，仍按硬编码偏移写入")
    except Exception:
        pass

    make_backup(img_path)
    with open(img_path, "r+b") as f:
        for fr in range(start_f, end_f + 1):
            off = RES_BASE + FRAME0_OFF + fr * FRAME_SIZE
            f.seek(off)
            f.write(blob)
            print(f"  帧 {fr:02d}: 写入偏移 0x{off:x}")

    print(f"\n✅ 完成！已替换帧 {start_f}~{end_f}")
    print("   现在可以刷入设备测试")

# ==================== 模式二：主题资源替换 ====================
def theme_mode(img_path, key, png_path):
    if not os.path.isfile(MANIFEST):
        print(f"错误：未找到 {MANIFEST}")
        print("      请先运行: python3 theme_extract.py <固件>")
        sys.exit(1)
    manifest = json.load(open(MANIFEST))

    if key.startswith("#"):
        idx = int(key[1:])
        targets = [e for e in manifest if e["index"] == idx]
    elif key.startswith("ALL:"):
        base = key[4:]
        names = {base, "B"+base, "C_"+base, "D_"+base, "E_"+base}
        targets = [e for e in manifest if norm(e["name"]) in names]
    elif len(key) > 1 and key[0] in "ABCDEG" and key[1] == ":":
        theme, base = key[0], key[2:]
        targets = [e for e in manifest
                   if e["theme"] == theme and norm(e["name"]) == base]
    elif key.endswith("*"):
        pre = key[:-1]
        targets = [e for e in manifest if norm(e["name"]).startswith(pre)]
    else:
        targets = [e for e in manifest if norm(e["name"]) == key]

    if not targets:
        print(f"未找到匹配资源: {key}")
        print("提示: grep -i 关键词 theme_dump/resources.tsv 先查名字")
        sys.exit(1)

    print(f"匹配 {len(targets)} 项:")
    for t in targets:
        print(f"  #{t['index']:4d} [{t['theme']}] {t['name']}"
              f"  {t['width']}x{t['height']}")

    file_size = check_image_file(img_path)
    src = load_png(png_path)
    make_backup(img_path)

    with open(img_path, "r+b") as f:
        for e in targets:
            w, h, dlen = e["width"], e["height"], e["datalen"]
            abs_off = RES_BASE + e["offset"]
            if dlen != w * h * 2:
                print(f"  ✗ #{e['index']} {e['name']}: 非原始RGB565"
                      f"（dlen={dlen}, 期望{w*h*2}），跳过")
                continue
            if abs_off + dlen > file_size:
                print(f"  ✗ #{e['index']} {e['name']}: 偏移超出文件范围，跳过")
                continue
            blob = encode_rgb565(src, w, h)
            f.seek(abs_off)
            f.write(blob)
            print(f"  ✓ #{e['index']:4d} [{e['theme']}] {e['name']}"
                  f"  {w}x{h} @ 0x{abs_off:x}")

    print("✅ 完成")

# ==================== 入口 ====================
def interactive():
    """无参数时进入交互式开机帧替换（兼容原 replace_startup.py）"""
    img_path = ask("固件镜像文件名", default="HIFIEC39.IMG",
                   validator=os.path.isfile)
    png_path = ask("Logo 图片文件名", validator=os.path.isfile)
    start_f = int(ask("替换起始帧 (Logo渐显建议从2开始)", default=2,
                      validator=lambda s: is_int(s) and FRAME_MIN <= int(s) <= FRAME_MAX))
    end_f = int(ask("替换结束帧 (建议6)", default=6,
                    validator=lambda s: is_int(s) and FRAME_MIN <= int(s) <= FRAME_MAX))
    frame_mode(img_path, png_path, start_f, end_f)

if __name__ == "__main__":
    argv = sys.argv[1:]

    # 模式一：4 个参数且后两个都是数字 → 开机帧替换
    if len(argv) == 4 and is_int(argv[2]) and is_int(argv[3]):
        frame_mode(argv[0], argv[1], int(argv[2]), int(argv[3]))
    # 模式二：3 个参数 → 主题资源替换
    elif len(argv) == 3:
        theme_mode(argv[0], argv[1], argv[2])
    # 无参数 → 交互式（帧替换）
    elif len(argv) == 0:
        interactive()
    else:
        print(__doc__)
        sys.exit(1)

