#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Echo Mini 固件主题资源提取器 v2.0
=================================
v2.0 变更
  * 导出文件名统一为 <主题>_<主题内序号>，例：A 主题第 12 项 → A_0012_MUSIC_BACKGROUND.png
    同一序号在各主题中代表同一种资源（A_0012 / B_0012 / C_0012 是各自主题的同一角色）
  * manifest.json 新增 theme_start / local 字段
  * resources.tsv 新增 local 列
  * 每个主题目录额外生成 _index.tsv（序号速查表）
  * --naming {local,global}  默认 local（v2 新命名）；global 为 v1 旧命名

用法
  python3 theme_extract.py                        # HIFIEC39.IMG → theme_dump/
  python3 theme_extract.py echo.img -o dump2
  python3 theme_extract.py --manifest-only        # 只重建清单，不导出图片
  python3 theme_extract.py --naming global        # 保留 v1 全局序号命名
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
RES_BASE      = 0x9BCD12
RES_COUNT_OFF = 0x10
IDX_OFF       = 0x20
IDX_SIZE      = 16
NAME_TABLE    = 0x1F98CB8
NAME_SIZE     = 108
NAME_LEN      = 44
SEG_END       = 0x1FC36FA

THEME_TAGS = ["ASTYLE", "BSTYLE", "CSTYLE", "DSTYLE", "ESTYLE"]
THEME_LET  = "ABCDE"
GLOBAL_LET = "G"
MAX_WH     = 4096

# ==================== 名字处理 ====================
_PAT_FULL = re.compile(r"_\([\d\s.,]*\)\.BMP$", re.I)
_PAT_BMP  = re.compile(r"\.BMP$", re.I)

def clean_name(raw: str) -> str:
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
                    help="只重建 manifest.json / resources.tsv / _index.tsv")
    ap.add_argument("--naming", choices=["local", "global"], default="local",
                    help="local=主题内序号（v2 默认），global=全局序号（v1）")
    args = ap.parse_args()

    data = open(args.image, "rb").read()
    print(f"读取固件: {args.image}  ({len(data)/1024/1024:.1f} MB)")

    if data[RES_BASE:RES_BASE+len(RES_MAGIC)] != RES_MAGIC:
        print(f"✗ 资源区魔数不匹配（期望 {RES_MAGIC!r}）")
        sys.exit(1)

    count = struct.unpack_from("<I", data, RES_BASE + RES_COUNT_OFF)[0]
    print(f"条目总数: {count}")

    # ---------- 解析 ----------
    entries = []
    for i in range(count):
        noff = NAME_TABLE + i * NAME_SIZE
        raw_name = data[noff:noff+NAME_LEN].split(b"\0")[0].decode("ascii", "replace")

        ioff = RES_BASE + IDX_OFF + i * IDX_SIZE
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
    print(f"宽高合理的条目: {sane}/{count}")

    # ---------- STYLE 分界 ----------
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

    # ---------- 主题划分 + 主题内序号 ----------
    theme_starts = {GLOBAL_LET: 0}
    for let, b in zip(THEME_LET, bounds):
        theme_starts[let] = b

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
        e["theme_start"] = theme_starts[e["theme"]]
        e["local"] = e["index"] - e["theme_start"]

    cnt = Counter(e["theme"] for e in entries)
    print("主题条目数: " +
          "  ".join(f"{k}={cnt.get(k, 0)}" for k in [GLOBAL_LET] + list(THEME_LET)))
    print(f"全局共享区: #0~#{bounds[0]-1}（开机/关机/充电画面，五套主题共用）")

    sizes = {k: cnt.get(k, 0) for k in THEME_LET}
    if len(set(sizes.values())) == 1:
        print(f"✓ 五套主题各 {sizes['A']} 项，划分正常")
    else:
        print(f"⚠ 各主题条目数不一致: {sizes}（该固件主题可能不对称，无碍）")

    # ---------- 导出文件名规则 ----------
    def out_stem(e):
        if args.naming == "global":
            return f"{e['index']:04d}_{safe_fname(e['name'])}"
        return f"{e['theme']}_{e['local']:04d}_{safe_fname(e['name'])}"

    # ---------- 导出 ----------
    os.makedirs(args.out, exist_ok=True)
    n_png = n_bin = 0
    if not args.manifest_only:
        from PIL import Image  # noqa: F401
        for e in entries:
            tdir = os.path.join(args.out, e["theme"])
            os.makedirs(tdir, exist_ok=True)
            stem = out_stem(e)

            w, h, dlen, off = e["width"], e["height"], e["datalen"], e["offset"]
            start = RES_BASE + off
            need  = w * h * 2

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

    # ---------- 每主题 _index.tsv ----------
    for th in [GLOBAL_LET] + list(THEME_LET):
        items = [e for e in entries if e["theme"] == th]
        if not items:
            continue
        tdir = os.path.join(args.out, th)
        os.makedirs(tdir, exist_ok=True)
        with open(os.path.join(tdir, "_index.tsv"), "w") as f:
            f.write("local\tglobal\tname\twidth\theight\tbytes\tformat\tfile\n")
            for e in items:
                f.write(f"{e['local']:04d}\t{e['index']}\t{e['name']}\t"
                        f"{e['width']}\t{e['height']}\t{e['datalen']}\t"
                        f"{e['format']}\t{e['file']}\n")

    # ---------- 写清单 ----------
    json.dump(entries, open(os.path.join(args.out, "manifest.json"), "w"),
              indent=1, ensure_ascii=False)

    with open(os.path.join(args.out, "resources.tsv"), "w") as f:
        f.write("theme\tlocal\tindex\tname\twidth\theight\toffset\tdatalen\tformat\n")
        for e in entries:
            f.write(f"{e['theme']}\t{e['local']:04d}\t{e['index']}\t{e['name']}\t"
                    f"{e['width']}\t{e['height']}\t0x{e['offset']:x}\t"
                    f"{e['datalen']}\t{e['format']}\n")

    # ---------- 汇总 ----------
    print(f"\n{'仅重建清单，未导出图片' if args.manifest_only else f'导出完成: {n_png} PNG, {n_bin} BIN'}")
    print(f"命名方式: {'主题内序号（<主题>_<序号>_<名称>）' if args.naming=='local' else '全局序号（v1 风格）'}")
    print(f"输出: {args.out}/")
    print(f"      manifest.json / resources.tsv / G/A/B/C/D/E/（含 _index.tsv）")

    suspects = [e for e in entries if e["suspect"]]
    if suspects:
        print(f"\n注意: {len(suspects)} 项名字为源码残片（用序号定位最可靠）")
        for e in suspects[:5]:
            print(f"      [{e['theme']}] local={e['local']:04d} "
                  f"#{e['index']:4d} {e['name_raw']!r}")

    print("\n常用资源速查（各主题同序号）:")
    for key in ("MAINMENUPAGE10", "MUSIC_BACKGROUND", "BROWSER_BACKGROUND",
                "USB_BACKGROUND", "MUSIC_BOTTOM", "VOLNUM_00"):
        hit = next((e for e in entries if e["name"] == key and e["theme"] == "A"), None)
        if hit:
            print(f"      A_{hit['local']:04d} = B_{hit['local']:04d} = ... "
                  f"{key:22s} {hit['width']}x{hit['height']}")
        else:
            print(f"      ----  {key:22s} 未找到")

if __name__ == "__main__":
    main()

