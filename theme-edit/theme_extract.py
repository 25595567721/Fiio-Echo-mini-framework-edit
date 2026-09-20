#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Echo Mini 固件主题资源提取器
============================
  1. 解析 ROCK26IMAGERES 容器（索引表为权威元数据，名称表提供名字）
  2. 规范化资源名（去掉 _(x,y).BMP 尾巴）
  3. 按 ASTYLE/BSTYLE/CSTYLE/DSTYLE/ESTYLE 序号区间划分主题 G/A/B/C/D/E
  4. RGB565 资源导出 PNG，异常格式存 .bin
  5. 生成 manifest.json + resources.tsv

用法：
  python3 theme_extract.py                       # HIFIEC39.IMG → theme_dump/
  python3 theme_extract.py echo.img -o dump2
  python3 theme_extract.py --manifest-only       # 只重建清单
"""
import argparse
import json
import os
import re
import struct
import sys
from collections import Counter

# ==================== 固件常量（Echo Mini V3.9.0 / HIFIEC39.IMG）====================
RES_MAGIC     = b"ROCK26IMAGERES  "
RES_BASE      = 0x9BCD12   # 容器起始（06_big 段内绝对偏移）
RES_COUNT_OFF = 0x10       # u32 条目总数
IDX_OFF       = 0x20       # 索引表起始，每项 16B: [w][h][dlen][doff]
IDX_SIZE      = 16
NAME_TABLE    = 0x1F98CB8  # 名称表起始（条目 #0 = POWERON0）
NAME_SIZE     = 108
NAME_LEN      = 44         # 名字字段长度
SEG_END       = 0x1FC36FA  # 06_big 段结束（完整性检查用）

THEME_TAGS = ["ASTYLE", "BSTYLE", "CSTYLE", "DSTYLE", "ESTYLE"]
THEME_LET  = "ABCDE"
GLOBAL_LET = "G"           # 全局共享区（开机/关机/充电等）
MAX_WH     = 4096          # 宽高合理性上限

# ==================== 名字处理 ====================
_PAT_FULL = re.compile(r"_\([\d\s.,]*\)\.BMP$", re.I)
_PAT_BMP  = re.compile(r"\.BMP$", re.I)

def clean_name(raw: str) -> str:
    """'MUSIC_BACKGROUND_(0,0).BMP' → 'MUSIC_BACKGROUND'"""
    return _PAT_BMP.sub("", _PAT_FULL.sub("", raw)).strip()

def is_suspect(n: str) -> bool:
    return (not n) or bool(re.search(r"[(),]", n))

def safe_fname(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.\-]", "_", s) or "unnamed"

# ==================== RGB565 解码 ====================
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

def decode565(pix: bytes, w: int, h: int):
    """RGB565 小端 → PIL Image"""
    from PIL import Image
    if _HAS_NUMPY:
        a = np.frombuffer(pix, dtype="<u2").astype(np.uint32)
        r = ((a >> 3) & 0x1F) << 3
        g = (((a & 7) << 3) | ((a >> 13) & 7)) << 2
        b = ((a >> 8) & 0x1F) << 3
        rgb = np.stack([r, g, b], -1).astype(np.uint8).reshape(h, w, 3)
        return Image.fromarray(rgb, "RGB")
    vals = struct.unpack(f"<{w*h}H", pix)
    buf = bytearray(w * h * 3)
    for p, v in enumerate(vals):
        buf[p*3]   = ((v >> 3) & 0x1F) << 3
        buf[p*3+1] = ((((v & 7) << 3) | ((v >> 13) & 7))) << 2
        buf[p*3+2] = ((v >> 8) & 0x1F) << 3
    return Image.frombytes("RGB", (w, h), bytes(buf))

# ==================== 主流程 ====================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image", nargs="?", default="HIFIEC39.IMG",
                    help="固件镜像（默认 HIFIEC39.IMG）")
    ap.add_argument("-o", "--out", default="theme_dump", help="输出目录")
    ap.add_argument("--manifest-only", action="store_true",
                    help="只重建 manifest.json / resources.tsv，不导出图片")
    args = ap.parse_args()

    data = open(args.image, "rb").read()
    print(f"读取固件: {args.image}  ({len(data)/1024/1024:.1f} MB)")

    # ---------- 魔数 ----------
    if data[RES_BASE:RES_BASE+len(RES_MAGIC)] != RES_MAGIC:
        print(f"✗ 资源区魔数不匹配（期望 {RES_MAGIC!r}）")
        sys.exit(1)

    count = struct.unpack_from("<I", data, RES_BASE + RES_COUNT_OFF)[0]
    print(f"条目总数: {count}")

    # ---------- 解析：名字取自名称表，元数据取自索引表 ----------
    entries, mismatch = [], 0
    for i in range(count):
        noff = NAME_TABLE + i * NAME_SIZE
        raw_name = data[noff:noff+NAME_LEN].split(b"\0")[0].decode("ascii", "replace")

        ioff = RES_BASE + IDX_OFF + i * IDX_SIZE
        # 索引表项 16B: [wh:u32][?:u32][dlen:u32][doff:u32]
        # wh 低 16 位 = 宽，高 16 位 = 高
        wh, _reserved, dlen, doff = struct.unpack_from("<IIII", data, ioff)
        w = wh & 0xFFFF
        h = (wh >> 16) & 0xFFFF



        entries.append({
            "index":    i,
            "name":     clean_name(raw_name),
            "name_raw": raw_name,
            "suspect":  is_suspect(clean_name(raw_name)),
            "offset":   doff,
            "width":    w,
            "height":   h,
            "datalen":  dlen,
        })

    print("前 5 项解析结果（调试用）:")
    for e in entries[:5]:
        print(f"  #{e['index']:4d} {e['name']:20s} "
              f"{e['width']}x{e['height']} dlen={e['datalen']} off=0x{e['offset']:x}")

    sane = sum(1 for e in entries
               if 0 < e["width"] <= MAX_WH and 0 < e["height"] <= MAX_WH
               and RES_BASE + e["offset"] + e["width"]*e["height"]*2 <= len(data))
    print(f"宽高合理的条目: {sane}/{count}（这些将按 RGB565 导出 PNG）")

    # ---------- STYLE 分界（按实际序号排序） ----------
    style_entries = sorted(
        [e for e in entries if any(e["name_raw"].startswith(t) for t in THEME_TAGS)],
        key=lambda e: e["index"])
    print("STYLE 分界条目:")
    for se in style_entries:
        print(f"  #{se['index']:4d}  {se['name_raw']!r}")

    if len(style_entries) < 5:
        print(f"✗ 只找到 {len(style_entries)} 个 STYLE 分界，不足 5 个")
        sys.exit(1)

    bounds = sorted(se["index"] for se in style_entries[:5])   # [67,377,687,997,1307]

    # ---------- 主题划分（区间判定，修正 A=0/E=620） ----------
    def theme_of(i):
        if i < bounds[0]:
            return GLOBAL_LET
        for j in range(len(bounds)):
            lo = bounds[j]
            hi = bounds[j + 1] if j + 1 < len(bounds) else None
            if i >= lo and (hi is None or i < hi):
                return THEME_LET[j]
        return THEME_LET[-1]

    for e in entries:
        e["theme"] = theme_of(e["index"])

    cnt = Counter(e["theme"] for e in entries)
    print("主题条目数: " +
          "  ".join(f"{k}={cnt.get(k, 0)}" for k in ["G"] + list(THEME_LET)))
    print(f"全局共享区: #0~#{bounds[0]-1}（开机/关机/充电画面，五套主题共用）")

    sizes = {k: cnt.get(k, 0) for k in THEME_LET}
    if len(set(sizes.values())) == 1:
        print(f"✓ 五套主题各 {sizes['A']} 项，划分正常")
    else:
        print(f"⚠ 各主题条目数不一致: {sizes}（该固件主题可能不对称，无碍）")

    # ---------- 导出 ----------
    os.makedirs(args.out, exist_ok=True)
    n_png = n_bin = 0
    if not args.manifest_only:
        from PIL import Image  # noqa: F401
        for e in entries:
            tdir = os.path.join(args.out, e["theme"])
            os.makedirs(tdir, exist_ok=True)
            stem = f"{e['index']:04d}_{safe_fname(e['name'])}"

            w, h, dlen, off = e["width"], e["height"], e["datalen"], e["offset"]
            start = RES_BASE + off
            need  = w * h * 2

            # 宽高合理 → 一律按 RGB565 截取（索引表为权威）
            if 0 < w <= MAX_WH and 0 < h <= MAX_WH and start + need <= len(data):
                decode565(data[start:start+need], w, h) \
                    .save(os.path.join(tdir, stem + ".png"))
                e["format"], e["file"] = "rgb565", f"{e['theme']}/{stem}.png"
                n_png += 1
            elif dlen > 0 and start + dlen <= len(data):
                open(os.path.join(tdir, stem + ".bin"), "wb") \
                    .write(data[start:start+dlen])
                e["format"], e["file"] = "unknown", f"{e['theme']}/{stem}.bin"
                n_bin += 1
            else:
                e["format"], e["file"] = "bad", ""

    # ---------- 写清单 ----------
    json.dump(entries, open(os.path.join(args.out, "manifest.json"), "w"),
              indent=1, ensure_ascii=False)

    with open(os.path.join(args.out, "resources.tsv"), "w") as f:
        f.write("index\ttheme\tname\twidth\theight\toffset\tdatalen\tformat\n")
        for e in entries:
            f.write(f"{e['index']}\t{e['theme']}\t{e['name']}\t{e['width']}\t"
                    f"{e['height']}\t0x{e['offset']:x}\t{e['datalen']}\t"
                    f"{e['format']}\n")

    # ---------- 汇总 ----------
    print(f"\n{'仅重建清单，未导出图片' if args.manifest_only else f'导出完成: {n_png} PNG, {n_bin} BIN'}")
    print(f"输出: {args.out}/")
    print(f"      manifest.json / resources.tsv / G/A/B/C/D/E 文件夹")

    suspects = [e for e in entries if e["suspect"]]
    if suspects:
        print(f"\n注意: {len(suspects)} 项名字为源码残片（用序号 #N 定位最可靠）")
        for e in suspects[:5]:
            print(f"      #{e['index']:4d} [{e['theme']}] {e['name_raw']!r}")

    # ---------- 常用资源速查 ----------
    print("\n常用资源定位（A 主题）:")
    for key in ("MAINMENUPAGE10", "MUSIC_BACKGROUND", "BROWSER_BACKGROUND",
                "USB_BACKGROUND", "MUSIC_BOTTOM", "VOLNUM_00"):
        hit = next((e for e in entries
                    if e["name"] == key and e["theme"] == "A"), None)
        if hit:
            print(f"      #{hit['index']:4d}  {key:22s} "
                  f"{hit['width']}x{hit['height']}  [{hit['format']}]")
        else:
            print(f"      ----  {key:22s} 未找到")

if __name__ == "__main__":
    main()

