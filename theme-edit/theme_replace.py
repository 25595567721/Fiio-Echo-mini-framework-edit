#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
theme_replace.py — Echo Mini 固件资源替换工具 v2.3
==================================================

【核心变更 v2.3】
  * 不修改原固件：所有写入操作自动生成新文件 xxxNew.img
  * 若 xxxNew.img 已存在，自动命名为 xxx_2_New.img、xxx_3_New.img...
  * 原固件文件全程只读，作为天然备份

【模式一：开机帧替换】兼容 replace_startup.py
  python3 theme_replace.py <固件> <图片> <起始帧> <结束帧>
  python3 theme_replace.py                          # 无参数 → 交互式
  帧 0/1 = POWERON0/1（开机前导帧，必须纯黑）
  帧 2~41 = Z_POWERON0~39（40 帧开机动画）
  输出：生成 <固件>New.img，原文件不变

【模式二：主题资源替换】需 theme_dump/manifest.json
  python3 theme_replace.py <固件> <名称> <png>
  python3 theme_replace.py <固件> A:<名称> <png>
  python3 theme_replace.py <固件> ALL:<名称> <png>
  python3 theme_replace.py <固件> <前缀>* <png>
  python3 theme_replace.py <固件> #<全局序号> <png>
  输出：生成 <固件>New.img，原文件不变

【模式三：主题包导入】批量替换
  python3 theme_replace.py <资源文件夹> <主题>            # 固件自动识别
  python3 theme_replace.py <固件> <资源文件夹> <主题>      # 显式指定固件
  文件夹内按"文件名中第一个数字"作为主题内序号逐项替换，未提供的序号保留原样。
  输出：生成 <固件>New.img，原文件不变

【模式四：列出主题序号】
  python3 theme_replace.py --list B

【文件名变换标记】★ v2.2/v2.3
  所有标记写在图片文件名里，可任意组合，大小写不敏感：

  适配方式（覆盖 --fit 默认值）
    fit1 = stretch  直接拉伸填满（可能变形）
    fit2 = contain  等比缩放 + 居中留边（不失真，可能有边）
    fit3 = cover    等比放大 + 中心裁剪（填满不失真，裁掉边缘）

  整体缩放（不写 = 1 倍）
    s = 0.5 倍    m = 0.75 倍    l = 1.25 倍
    注意：s/m/l 必须作为独立单词出现（下划线/横线/点/空格分隔），
          所以 MUSIC_BACKGROUND 里的 m 不会误触发。

  像素位移（相对画面中心）
    l10 = 左移 10px   r10 = 右移 10px
    u10 = 上移 10px   d10 = 下移 10px
    也支持全称：left10 / right10 / up10 / down10
    可连写：l10u20 = 左移10 且 上移20

  处理顺序：① 适配到目标尺寸 → ② 以中心为基准缩放 → ③ 平移，留白用 --bg 填充

  示例：
    A_0012.png                默认适配，1 倍，不位移
    A_0012_fit2.png           等比留边
    A_0012_fit2s.png          等比留边 + 0.5 倍
    A_0045_fit3_l10u20.png    等比裁剪 + 1.25 倍 + 左移10 上移20
    0067_battery-d5.png       默认适配 + 下移 5px

【可选参数】
  --fit {stretch,contain,cover}  未带 fit 标记时的默认适配方式（默认 stretch）
  --bg RRGGBB                    留白填充色（默认 000000）
  --force                        文件名主题字母与目标不符时也强行导入
  --dry-run                      只预览不写入
  --preview [目录]               预览时把合成结果存成 PNG（默认 theme_preview/）
  -r, --recursive                递归扫描子目录
  --firmware <文件>              指定固件（模式三自动识别用）
  --list <主题>                  列出该主题的序号表
"""
import json
import os
import re
import shutil
import sys

from PIL import Image

# ==================== 固件常量 ====================
RES_BASE     = 0x9BCD12
FRAME0_OFF   = 0x6930
FRAME_SIZE   = 0x1A900
W, H         = 320, 170
FRAME_MIN    = 0
FRAME_MAX    = 41
BLACK_FRAMES = (0, 1)
MANIFEST     = os.path.join("theme_dump", "manifest.json")

IMG_EXT   = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
ALL_THEME = "GABCDE"

# ---- 文件名标记 ----
FIT_TAGS   = {"fit1": "stretch", "fit2": "contain", "fit3": "cover"}
SCALE_TAGS = {"s": 0.5, "m": 0.75, "l": 1.25}
DIR_CN     = {"l": "左", "r": "右", "u": "上", "d": "下"}

_FIT_TOKEN   = re.compile(r"^fit[_-]?([123])$", re.I)
_TOKEN_SPLIT = re.compile(r"[_\-\s.]+")
_SHIFT_TOKEN = re.compile(r"(?:([lrud])|(left|right|up|down))[_-]?(\d+)", re.I)

_PAT_FULL = re.compile(r"_\([\d\s.,]*\)\.BMP$", re.I)
_PAT_BMP  = re.compile(r"\.BMP$", re.I)

def norm(n):
    return _PAT_BMP.sub("", _PAT_FULL.sub("", n)).strip()

# ==================== RGB565 编码 ====================
def encode_rgb565(img, w, h):
    img = img.convert("RGB")
    if img.size != (w, h):
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
        buf = bytearray(w * h * 2)
        for p in range(w * h):
            r, g, b = raw[p*3] >> 3, raw[p*3+1] >> 2, raw[p*3+2] >> 3
            buf[p*2]   = (r << 3) | (g >> 3)
            buf[p*2+1] = ((g & 7) << 5) | b
        return bytes(buf)

# ==================== 三步变换：适配 → 缩放 → 位移 ====================
def transform_image(img, w, h, fit="stretch", scale=1.0, shift=(0, 0), bg=(0, 0, 0)):
    """
    1) fit   : 把源图适配成 w×h 的整幅画面（stretch/contain/cover）
    2) scale : 对适配后的画面整体缩放，以中心为基准，四周补 bg
    3) shift : 再整体平移 dx/dy，露出部分补 bg
    返回 (结果图, 说明文字)
    """
    src = img.convert("RGB")
    notes = []

    # ---------- 1) 适配 ----------
    sw, sh = src.size
    if sw <= 0 or sh <= 0:
        raise ValueError(f"图片尺寸非法: {sw}x{sh}")

    if (sw, sh) == (w, h):
        notes.append("原尺寸")
    elif fit == "stretch":
        src = src.resize((w, h), Image.LANCZOS)
        notes.append(f"拉伸{sw}x{sh}→{w}x{h}")
    else:
        sc = min(w / sw, h / sh) if fit == "contain" else max(w / sw, h / sh)
        nw, nh = max(1, round(sw * sc)), max(1, round(sh * sc))
        tmp = src.resize((nw, nh), Image.LANCZOS)
        if fit == "contain":
            canvas = Image.new("RGB", (w, h), bg)
            canvas.paste(tmp, ((w - nw) // 2, (h - nh) // 2))
            notes.append(f"等比{sc:.3f}留边{sw}x{sh}→{nw}x{nh}")
        else:
            left, top = max(0, (nw - w) // 2), max(0, (nh - h) // 2)
            tmp = tmp.crop((left, top, left + w, top + h))
            notes.append(f"等比{sc:.3f}裁剪{sw}x{sh}→{w}x{h}")
        src = tmp

    # ---------- 2) 缩放 ----------
    if abs(scale - 1.0) > 1e-6:
        nw, nh = max(1, round(w * scale)), max(1, round(h * scale))
        scaled = src.resize((nw, nh), Image.LANCZOS)
        canvas = Image.new("RGB", (w, h), bg)
        canvas.paste(scaled, ((w - nw) // 2, (h - nh) // 2))
        src = canvas
        notes.append(f"缩放x{scale:g}→{nw}x{nh}")

    # ---------- 3) 位移 ----------
    dx, dy = int(shift[0]), int(shift[1])
    if dx or dy:
        canvas = Image.new("RGB", (w, h), bg)
        canvas.paste(src, (dx, dy))      # 越界自动裁剪
        src = canvas
        notes.append(f"位移({dx:+d},{dy:+d})")

    return src, " | ".join(notes)

# ==================== 通用工具 ====================
def prepare_output(img_path):
    """
    不改动旧固件：复制出新文件，返回新文件路径。
    HIFIEC39.IMG → HIFIEC39New.img → HIFIEC39_2_New.img → ...
    """
    root, ext = os.path.splitext(img_path)
    ext = ext or ".img"

    out = f"{root}New{ext}"
    if os.path.exists(out):
        n = 2
        while os.path.exists(f"{root}_{n}_New{ext}"):
            n += 1
        out = f"{root}_{n}_New{ext}"

    shutil.copy2(img_path, out)
    print(f"  新固件: {out}  （旧文件保持不变）")
    return out

def check_firmware(img_path):
    if not os.path.isfile(img_path):
        print(f"错误：固件文件不存在 {img_path}")
        sys.exit(1)
    size = os.path.getsize(img_path)
    print(f"  ✓ 固件: {img_path} ({size/1024/1024:.1f} MB)")
    return size

def find_firmware(explicit=None):
    if explicit:
        return explicit
    for c in ("echo.img", "HIFIEC39.IMG", "ECHO.IMG", "Echo.img"):
        if os.path.isfile(c):
            return c
    cands = sorted(f for f in os.listdir(".")
                   if f.lower().endswith(".img") and os.path.isfile(f))
    if len(cands) == 1:
        return cands[0]
    if not cands:
        print("错误：当前目录未找到固件（*.img），请用 --firmware 指定")
    else:
        print(f"错误：当前目录有多个固件，请用 --firmware 指定：{cands}")
    sys.exit(1)

def load_png(png_path):
    if not os.path.isfile(png_path):
        print(f"错误：图片文件不存在 {png_path}")
        sys.exit(1)
    return Image.open(png_path)

def load_manifest():
    if not os.path.isfile(MANIFEST):
        print(f"错误：未找到 {MANIFEST}")
        print("      请先运行: python3 theme_extract.py <固件>")
        sys.exit(1)
    manifest = json.load(open(MANIFEST))

    # 兼容旧版 manifest：缺 local / theme_start 时按主题起始序号自动补算
    if manifest and "local" not in manifest[0]:
        theme_starts = {}
        for e in manifest:
            t = e.get("theme", "G")
            theme_starts[t] = min(theme_starts.get(t, 10**9), e["index"])
        for e in manifest:
            t = e.get("theme", "G")
            e["theme_start"] = theme_starts[t]
            e["local"] = e["index"] - theme_starts[t]
        print("⚠ manifest.json 为旧版格式（无 local 字段），已自动换算序号；")
        print("  建议抽空重跑: python3 theme_extract.py <固件> --manifest-only")

    return manifest

def warn_if_not_black(img, frames, label=""):
    if not any(f in BLACK_FRAMES for f in frames):
        return
    from PIL import ImageStat
    mean = ImageStat.Stat(img.convert("L").resize((32, 17))).mean[0]
    if mean > 8:
        print(f"  ⚠⚠ 警告：{label} 是开机前导帧，必须为纯黑图片！")
        print(f"     当前合成结果平均亮度 {mean:.0f}/255，刷入后可能无法安装或启动！")

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

def save_preview(img, theme, local, preview_dir):
    if not preview_dir:
        return
    os.makedirs(preview_dir, exist_ok=True)
    img.save(os.path.join(preview_dir, f"{theme}_{local:04d}.png"))

# ==================== 文件名解析 ====================
def parse_image_name(fname):
    """
    解析文件名中的序号、主题字母与全部变换标记。
    返回 dict: num, letter, fit, scale, shift, tags
    """
    stem = os.path.splitext(os.path.basename(fname))[0]
    tokens = [t for t in _TOKEN_SPLIT.split(stem) if t]

    fit, scale = None, 1.0
    dx = dy = 0
    tags, rest = [], []

    for t in tokens:
        m = _FIT_TOKEN.match(t)                       # fit1/2/3
        if m:
            fit = FIT_TAGS[f"fit{m.group(1)}"]
            tags.append(f"{t.lower()}→{fit}")
            continue

        tl = t.lower()
        if tl in SCALE_TAGS:                          # 独立单词 s / m / l
            scale = SCALE_TAGS[tl]
            tags.append(f"{tl}→x{scale:g}")
            continue

        hits = _SHIFT_TOKEN.findall(t)                # l10 / u30 / left20
        if hits and len("".join((a or b) + c for a, b, c in hits)) == len(t):
            for a, b, c in hits:
                d = (a or b).lower()[0]
                n = int(c)
                if d == "l":   dx -= n
                elif d == "r": dx += n
                elif d == "u": dy -= n
                else:          dy += n
                tags.append(f"{t}→{DIR_CN[d]}移{n}px")
            continue

        rest.append(t)

    # ---- 从剩余单词里解析序号（放宽：1~4 位数字均可）----
    joined = "_".join(rest)
    num, letter = None, None

    # 模式1：字母开头，紧跟数字（如 A12, B_0047, G0002）
    m = re.match(r"^([A-Za-z]+)[_\-]?(\d{1,4})(?:_|$|\.)", joined)
    if m:
        l = m.group(1).upper()
        num = int(m.group(2))
        if len(l) == 1 and l in ALL_THEME:
            letter = l
    else:
        # 模式2：纯数字开头或独立数字（如 47.png, 0047_bg.png, 12.jpg）
        m = re.match(r"^(\d{1,4})(?:_|$|\.)", joined)
        if m:
            num = int(m.group(1))
        else:
            # 模式3：文件名中任意位置的独立数字（保底）
            m = re.search(r"(?:^|[^\d])(\d{1,4})(?:[^\d]|$)", joined)
            if m:
                num = int(m.group(1))

    return {"num": num, "letter": letter, "fit": fit, "scale": scale,
            "shift": (dx, dy), "tags": tags}

        
def scan_folder(folder, recursive=False):
    """返回 (found, problems)；found[num] = (路径, 主题字母, 参数字典)"""
    files = []
    if recursive:
        for root, _dirs, names in os.walk(folder):
            files += [os.path.join(root, n) for n in names]
    else:
        files = [os.path.join(folder, n) for n in os.listdir(folder)
                 if os.path.isfile(os.path.join(folder, n))]
    files = [f for f in files
             if f.lower().endswith(IMG_EXT) and not os.path.basename(f).startswith(".")]

    found, problems = {}, []
    for f in sorted(files):
        p = parse_image_name(f)
        if p["num"] is None:
            problems.append((f, "文件名中无数字，无法定位"))
            continue
        if p["num"] in found:
            problems.append((f, f"序号 {p['num']} 重复，后者覆盖前者"))
        found[p["num"]] = (f, p["letter"], p)
    return found, problems

# ==================== 模式一：开机帧替换 ====================
def frame_mode(img_path, png_path, start_f, end_f):
    if not (FRAME_MIN <= start_f <= FRAME_MAX and FRAME_MIN <= end_f <= FRAME_MAX):
        print(f"错误：帧号必须在 {FRAME_MIN}~{FRAME_MAX} 之间")
        sys.exit(1)
    if start_f > end_f:
        start_f, end_f = end_f, start_f

    file_size = check_firmware(img_path)
    need_size = RES_BASE + FRAME0_OFF + (FRAME_MAX + 1) * FRAME_SIZE
    if file_size < need_size:
        print(f"错误：文件太小，至少需要 {need_size} 字节，实际 {file_size}")
        sys.exit(1)

    p = parse_image_name(png_path)
    fit = p["fit"] or "stretch"
    if p["tags"]:
        print(f"  文件名标记: {', '.join(p['tags'])}")

    print(f"\n处理中：{img_path} ← {png_path}  帧 {start_f}~{end_f}")
    img = load_png(png_path)
    out, note = transform_image(img, W, H, fit, p["scale"], p["shift"], (0, 0, 0))
    print(f"  变换: {note}")
    warn_if_not_black(out, range(start_f, end_f + 1), f"帧 {start_f}~{end_f}")
    blob = encode_rgb565(out, W, H)
    assert len(blob) == FRAME_SIZE

    try:
        m = json.load(open(MANIFEST))
        for fr in (start_f, end_f):
            e = m[fr]
            expect = FRAME0_OFF + fr * FRAME_SIZE
            if e["offset"] != expect:
                print(f"  ⚠ manifest 条目 #{fr} ({e['name']}) 偏移 0x{e['offset']:x}"
                      f" ≠ 预期 0x{expect:x}，仍按硬编码偏移写入")
    except Exception:
        pass

    # ---------- 复制新固件并写入 ----------
    out_path = prepare_output(img_path)
    with open(out_path, "r+b") as f:
        for fr in range(start_f, end_f + 1):
            off = RES_BASE + FRAME0_OFF + fr * FRAME_SIZE
            f.seek(off)
            f.write(blob)
            print(f"  帧 {fr:02d}: 写入偏移 0x{off:x}")

    print(f"\n✅ 完成！已替换帧 {start_f}~{end_f}")
    print(f"   新固件: {out_path}  ← 刷入这个")
    print(f"   原固件: {img_path}  （未改动，留作备份）")

# ==================== 模式二：按键名替换 ====================
def theme_key_mode(img_path, key, png_path, opts):
    manifest = load_manifest()

    if key.startswith("#"):
        idx = int(key[1:])
        targets = [e for e in manifest if e["index"] == idx]
    elif key.startswith("ALL:"):
        base = key[4:]
        targets = [e for e in manifest if norm(e["name"]) == base]
    elif len(key) > 1 and key[0].upper() in ALL_THEME and key[1] == ":":
        theme, base = key[0].upper(), key[2:]
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

    p = parse_image_name(png_path)
    fit = p["fit"] or opts["fit"]
    if p["tags"]:
        print(f"文件名标记: {', '.join(p['tags'])}")

    print(f"匹配 {len(targets)} 项（fit={fit}，缩放 x{p['scale']:g}，"
          f"位移 {p['shift'][0]:+d},{p['shift'][1]:+d}）:")
    for t in targets:
        print(f"  [{t['theme']}] local={t.get('local', -1):04d} #{t['index']:4d} "
              f"{t['name']}  {t['width']}x{t['height']}")

    file_size = check_firmware(img_path)
    src = load_png(png_path)

    if opts["dry_run"]:
        if opts["preview"]:
            for t in targets:
                try:
                    out, note = transform_image(src, t["width"], t["height"],
                                                fit, p["scale"], p["shift"], opts["bg"])
                    save_preview(out, t["theme"], t.get("local", t["index"]),
                                 opts["preview"])
                    print(f"  预览 [{t['theme']}] {t['name']}: {note}")
                except Exception as ex:
                    print(f"  ✗ {t['name']}: {ex}")
            print(f"预览已保存至 {opts['preview']}/")
        else:
            print("（--dry-run，未写入）")
        return

    # ---------- 复制新固件并写入 ----------
    out_path = prepare_output(img_path)
    with open(out_path, "r+b") as f:
        for e in targets:
            w, h, dlen = e["width"], e["height"], e["datalen"]
            abs_off = RES_BASE + e["offset"]
            if dlen < w * h * 2:
                print(f"  ✗ #{e['index']} {e['name']}: 数据区小于图像"
                      f"（{dlen} < {w*h*2}），跳过")
                continue
            if abs_off + w * h * 2 > file_size:
                print(f"  ✗ #{e['index']} {e['name']}: 超出文件范围，跳过")
                continue
            out, note = transform_image(src, w, h, fit, p["scale"], p["shift"], opts["bg"])
            blob = encode_rgb565(out, w, h)
            f.seek(abs_off)
            f.write(blob)
            print(f"  ✓ [{e['theme']}] local={e.get('local', -1):04d} "
                  f"{e['name']}  {w}x{h} @0x{abs_off:x}  {note}")

    print(f"\n✅ 完成")
    print(f"   新固件: {out_path}  ← 刷入这个")
    print(f"   原固件: {img_path}  （未改动，留作备份）")

# ==================== 模式三：主题包导入 ====================
def theme_folder_mode(img_path, folder, theme, opts):
    theme = theme.strip().rstrip(":").upper()
    if theme not in ALL_THEME:
        print(f"错误：主题必须是 {'/'.join(ALL_THEME)} 之一，收到 {theme!r}")
        sys.exit(1)
    if not os.path.isdir(folder):
        print(f"错误：资源文件夹不存在 {folder}")
        sys.exit(1)

    manifest = load_manifest()
    items = {e["local"]: e for e in manifest if e["theme"] == theme}
    if not items:
        print(f"错误：manifest 中没有主题 {theme} 的资源")
        sys.exit(1)
    tmax = max(items)
    print(f"[模式三] 主题包导入")
    print(f"  目标主题: {theme}  （local 0000~{tmax:04d}，共 {len(items)} 项）")
    print(f"  默认适配: {opts['fit']}"
          f"（文件名可覆盖：fit1=stretch fit2=contain fit3=cover）")

    found, problems = scan_folder(folder, opts["recursive"])
    if not found:
        print(f"错误：{folder}/ 中没有可识别的图片"
              f"（支持 {'/'.join(IMG_EXT)}，文件名需含数字）")
        sys.exit(1)

    print(f"\n资源文件夹: {folder}/  识别到 {len(found)} 张图片")
    for f, why in problems:
        print(f"  ⚠ {why}: {f}")

    file_size = check_firmware(img_path)

    # ---------- 预检 ----------
    plan, skip = [], []
    for num in sorted(found):
        path, letter, p = found[num]
        e = items.get(num)
        if e is None:
            skip.append((num, path,
                         f"主题 {theme} 无 local={num:04d}（范围 0000~{tmax:04d}）"))
            continue
        if letter and letter != theme and not opts["force"]:
            skip.append((num, path,
                         f"文件名标的是 {letter} 主题，与目标 {theme} 不符"
                         f"（--force 可强行导入）"))
            continue
        if e["format"] != "rgb565":
            skip.append((num, path,
                         f"固件内该资源非 RGB565（format={e['format']}），无法安全替换"))
            continue
        abs_off = RES_BASE + e["offset"]
        need = e["width"] * e["height"] * 2
        if e["datalen"] < need or abs_off + need > file_size:
            skip.append((num, path, f"数据区异常（dlen={e['datalen']} need={need}）"))
            continue
        fit = p["fit"] or opts["fit"]
        plan.append((num, path, e, fit, p["scale"], p["shift"], p["tags"]))

    # ---------- 计划表 ----------
    print(f"\n{'序号':>5}  {'目标资源':<30} {'固件尺寸':<9} {'源图尺寸':<11} "
          f"{'适配':<8}{'缩放':<7}{'位移':<9}")
    print("-" * 104)
    for num, path, e, fit, scale, shift, tags in list(plan):
        try:
            with Image.open(path) as im:
                sw, sh = im.size
        except Exception as ex:
            skip.append((num, path, f"图片无法解码: {ex}"))
            plan = [q for q in plan if q[0] != num]
            continue
        shs = f"{shift[0]:+d},{shift[1]:+d}" if any(shift) else "-"
        print(f"{num:>5}  [{theme}] {e['name']:<22} "
              f"{e['width']}x{e['height']:<6} {sw}x{sh:<8} "
              f"{fit:<8}x{scale:<6g}{shs:<9}")

    # ---------- 文件名标记明细 ----------
    tagged = [(num, path, tags) for num, path, _e, _f, _s, _sh, tags in plan if tags]
    if tagged:
        print(f"\n检测到文件名标记（{len(tagged)} 项）:")
        for num, path, tags in tagged:
            print(f"  local={num:04d}  {os.path.basename(path)}  →  {', '.join(tags)}")

    if skip:
        print(f"\n跳过 {len(skip)} 项:")
        for num, path, why in skip:
            print(f"  ✗ local={num:04d}  {os.path.basename(path)}  —— {why}")

    kept = sorted(set(items) - {q[0] for q in plan})
    print(f"\n汇总: 替换 {len(plan)} 项 | 保留固件原样 {len(kept)} 项 | 跳过 {len(skip)} 项")

    if not plan:
        print("没有可替换项，退出")
        return

    # ---------- 预览 / 写入 ----------
    if opts["dry_run"]:
        if opts["preview"]:
            for num, path, e, fit, scale, shift, _tags in plan:
                try:
                    out, note = transform_image(Image.open(path), e["width"],
                                                e["height"], fit, scale, shift, opts["bg"])
                    save_preview(out, theme, num, opts["preview"])
                except Exception as ex:
                    print(f"  ✗ local={num:04d} 预览失败: {ex}")
            print(f"预览已保存至 {opts['preview']}/（{len(plan)} 张）")
        else:
            print("\n（--dry-run 预览结束，未写入任何数据；"
                  "加 --preview 可导出合成结果）")
        return

    # ---------- 复制新固件并写入 ----------
    out_path = prepare_output(img_path)
    ok = err = 0
    with open(out_path, "r+b") as f:
        for num, path, e, fit, scale, shift, _tags in plan:
            try:
                out, note = transform_image(Image.open(path), e["width"],
                                            e["height"], fit, scale, shift, opts["bg"])
                blob = encode_rgb565(out, e["width"], e["height"])
                if len(blob) != e["width"] * e["height"] * 2:
                    raise ValueError(f"编码长度异常 {len(blob)}")
                abs_off = RES_BASE + e["offset"]
                f.seek(abs_off)
                f.write(blob)
                ok += 1
                print(f"  ✓ local={num:04d} [{theme}] {e['name']}  "
                      f"{e['width']}x{e['height']} @0x{abs_off:x}  {note}")
            except Exception as ex:
                err += 1
                print(f"  ✗ local={num:04d} {os.path.basename(path)}: {ex}")

    print(f"\n✅ 完成：写入 {ok} 项，失败 {err} 项")
    print(f"   新固件: {out_path}  ← 刷入这个")
    print(f"   原固件: {img_path}  （未改动，留作备份）")
    if kept:
        preview = ", ".join(f"{n:04d}" for n in kept[:12])
        more = "" if len(kept) <= 12 else f" ... 共 {len(kept)} 项"
        print(f"   未提供的序号沿用固件原资源: {preview}{more}")

# ==================== 模式四：列出主题序号 ====================
def list_theme(theme):
    theme = theme.strip().rstrip(":").upper()
    manifest = load_manifest()
    items = [e for e in manifest if e["theme"] == theme]
    if not items:
        print(f"manifest 中没有主题 {theme}")
        sys.exit(1)
    print(f"主题 {theme}（共 {len(items)} 项）")
    print(f"{'local':>5}  {'global':>6}  {'名称':<34} {'尺寸':<10} format")
    print("-" * 78)
    for e in items:
        print(f"{e['local']:>5}  {e['index']:>6}  {e['name']:<34} "
              f"{e['width']}x{e['height']:<6} {e.get('format','')}")

# ==================== 参数解析 + 入口 ====================
def parse_opts(argv):
    opts = {"fit": "stretch", "bg": (0, 0, 0), "force": False,
            "dry_run": False, "recursive": False, "firmware": None,
            "list": None, "preview": None}
    positional = []
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--fit":
            i += 1
            if i >= len(argv) or argv[i] not in ("contain", "stretch", "cover"):
                print("错误：--fit 需要 contain / stretch / cover")
                sys.exit(1)
            opts["fit"] = argv[i]
        elif a.startswith("--fit="):
            v = a.split("=", 1)[1]
            if v not in ("contain", "stretch", "cover"):
                print("错误：--fit 需要 contain / stretch / cover")
                sys.exit(1)
            opts["fit"] = v
        elif a == "--bg":
            i += 1
            opts["bg"] = parse_color(argv[i])
        elif a.startswith("--bg="):
            opts["bg"] = parse_color(a.split("=", 1)[1])
        elif a == "--preview":
            if i + 1 < len(argv) and not argv[i + 1].startswith("-"):
                i += 1
                opts["preview"] = argv[i]
            else:
                opts["preview"] = "theme_preview"
        elif a.startswith("--preview="):
            opts["preview"] = a.split("=", 1)[1] or "theme_preview"
        elif a == "--firmware":
            i += 1
            opts["firmware"] = argv[i]
        elif a.startswith("--firmware="):
            opts["firmware"] = a.split("=", 1)[1]
        elif a == "--list":
            i += 1
            if i >= len(argv):
                print("错误：--list 需要主题字母")
                sys.exit(1)
            opts["list"] = argv[i]
        elif a.startswith("--list="):
            opts["list"] = a.split("=", 1)[1]
        elif a in ("--force", "-f"):
            opts["force"] = True
        elif a in ("--dry-run", "-n"):
            opts["dry_run"] = True
        elif a in ("-r", "--recursive"):
            opts["recursive"] = True
        elif a in ("-h", "--help"):
            print(__doc__)
            sys.exit(0)
        elif a.startswith("-") and len(positional) == 0 and a != "-":
            print(f"未知参数: {a}")
            print(__doc__)
            sys.exit(1)
        else:
            positional.append(a)
        i += 1
    return positional, opts

def parse_color(s):
    s = s.lstrip("#")
    if len(s) != 6:
        print(f"错误：颜色需要 6 位十六进制，如 000000，收到 {s!r}")
        sys.exit(1)
    return tuple(int(s[i:i+2], 16) for i in (0, 2, 4))

def interactive():
    img_path = ask("固件镜像文件名", default="HIFIEC39.IMG", validator=os.path.isfile)
    png_path = ask("Logo 图片文件名", validator=os.path.isfile)
    start_f = int(ask("替换起始帧 (Logo渐显建议从2开始)", default=2,
                      validator=lambda s: is_int(s) and FRAME_MIN <= int(s) <= FRAME_MAX))
    end_f = int(ask("替换结束帧 (建议6)", default=6,
                    validator=lambda s: is_int(s) and FRAME_MIN <= int(s) <= FRAME_MAX))
    frame_mode(img_path, png_path, start_f, end_f)

if __name__ == "__main__":
    argv, opts = parse_opts(sys.argv[1:])
    n = len(argv)

    if opts["list"]:
        list_theme(opts["list"])

    elif n == 0:
        interactive()

    # 模式三：2 参数且第 1 个是目录
    elif n == 2 and os.path.isdir(argv[0]):
        theme_folder_mode(find_firmware(opts["firmware"]), argv[0], argv[1], opts)

    # 模式三：3 参数且第 2 个是目录
    elif n == 3 and os.path.isdir(argv[1]):
        theme_folder_mode(argv[0], argv[1], argv[2], opts)

    # 模式一：4 参数且后两个是数字
    elif n == 4 and is_int(argv[2]) and is_int(argv[3]):
        frame_mode(argv[0], argv[1], int(argv[2]), int(argv[3]))

    # 模式二：3 参数
    elif n == 3:
        theme_key_mode(argv[0], argv[1], argv[2], opts)

    else:
        print(__doc__)
        sys.exit(1)

