# Fiio-Echo-mini-framework-edit
仅用于个人学习，对于Fiio一款ECHO mini播放器固件修改的研究。其中内容大多来自AI，侵权请联系\
本项目内容目前大多针对linux\
本项目中研究固件为echo mini v3.9.0 8g版本（HIFIEC39.IMG），其余版本的文件在大多区域类似，但目前并未研究

# 基础分析
## 1.固件基础数据
HIFIEC39.IMG：32 MiB，33554432 字节，65536 个扇区\
单元：扇区 / 1 * 512 = 512 字节\
扇区大小(逻辑/物理)：512 字节 / 512 字节\
I/O 大小(最小/最佳)：512 字节 / 512 字节\
### 关键资源：

POWERON0/1 —— 开机静态图（2张）\
Z_POWERON0 ~ Z_POWERON39 —— 开机动画帧（40帧！）{详情见start-frames}\
POWEROFF0_(0.0).BMP —— 关机画面\
MAINMENUPAGE10 ~ 50 —— 主菜单界面\
MUSIC_BACKGROUND/BOTTOM/... —— 播放界面
## 2.已解析出的镜像结构
头部（0x00–0x1FF）包含 "Rockchip"、"RKnano SDK 1.0" 标识，0x1F8 处有 "RKnanoFW" 目录表。根据头部里的 (偏移, 大小) 表项，数据段是一条连续链（我逐项验算过，每段的 起始+大小=下一段起始）\
另外 RKnanoFW 目录表项形如 (地址|0x03000000, 大小)，指向 head 区内的小文件。已验证连续性：0x4000+0x1AFC=0x5AFC、0x5AFC+0x18C50=0x1E74C。
<img width="1120" height="443" alt="dms-screenshot-1789840744564" src="https://github.com/user-attachments/assets/6dab85ce-279b-4f09-b07f-60ce0ca0ed4b" />
img镜像据此拆分为bin,位于img-out
## 3.索引表结构
+0  u32 width    = 0x140 = 320  ← 屏幕宽度\
+4  u32 height   = 0xAA  = 170  ← 屏幕高度（Echomini 是 320×170 横屏！）\
+8  u32 datalen  = 0x1A900       ← 压缩后数据长度\
+12 u32 dataoff  = 0x6930, 0x21230, 0x3BB30...  ← 像素位置（06_big.bin 内偏移）

## 4.资源地图

## a.主题资源
5 套主题资源（前缀不同，后3套是 D/E 重复）：
<img width="816" height="255" alt="dms-screenshot-1789841125974" src="https://github.com/user-attachments/assets/9fc42012-f005-41c4-8bf6-502665cf6318" />

# 镜像修改
### 要求
1.已安装python工具

linux安装python 可参考https://geek-blogs.com/blog/install-python-3-12-linux/ \
windows随便找个应用商店吧，我懒得打字<img width="41" height="40" alt="ZZZicon1" src="https://github.com/user-attachments/assets/74a8bcb1-f451-4339-b726-2e357e5e5e36" />






## 开机动画
### 基础信息
屏幕：320×170 横屏\
像素格式：RGB565（2 字节/像素）\
每帧大小：320 × 170 × 2 = 108,800 字节（0x1A900）\
Z_POWERON0 起始位置：BASE + 0x6930 = 0x9BCD12 + 0x6930 = 0x9C4642
### 固件动画提取
通过python3脚本实现


将动画逐帧输出到当前目录中[startupFrames]文件夹

    vim extract_all.py
    或
    nano extract_all.py
在当前目录创建python脚本，填入以下内容

    #!/usr/bin/env python3
    """提取 Z_POWERON0~39 全部 40 帧开机动画"""
    from PIL import Image
    import os

    IMG = "HIFIEC39.IMG"    
        # IMG填相对或绝对目录，此处默认为当前目录
    BASE = 0x9BCD12   # ROCK26IMAGERES 在固件中的绝对偏移
    OUT_DIR = "startupFrames"
    os.makedirs(OUT_DIR, exist_ok=True)

    W, H = 320, 170
    FRAME_SIZE = 0x1A900  # 108,800 bytes per frame

    with open(IMG, "rb") as f:
        f.seek(BASE + 0x6930)   # Z_POWERON0 像素数据起始
        for i in range(40):
            raw = f.read(FRAME_SIZE)
            if len(raw) < FRAME_SIZE:
                print(f"帧 {i}: 数据不足 ({len(raw)} bytes)")
                break
            # RGB565 -> RGB888
            rgb = bytearray(W * H * 3)
            for p in range(W * H):
                b1, b2 = raw[p*2], raw[p*2+1]
                r = (b1 >> 3) & 0x1F          # 5 bits
                g = ((b1 & 0x07) << 3) | ((b2 >> 5) & 0x07)  # 6 bits
                b = b2 & 0x1F                 # 5 bits
                rgb[p*3] = r << 3
                rgb[p*3+1] = g << 2
                rgb[p*3+2] = b << 3
            img = Image.frombytes("RGB", (W, H), bytes(rgb))
            img.save(f"{OUT_DIR}/poweron_{i:02d}.png")
            print(f"帧 {i:02d}: {len(raw)} bytes -> poweron_{i:02d}.png")

    # 显示第一帧和最后一帧的像素差异（确认是动画而非静态）
    img0 = Image.open(f"{OUT_DIR}/poweron_00.png")
    img39 = Image.open(f"{OUT_DIR}/poweron_39.png")
    diff = 0
    for p in range(W * H):
        if img0.getpixel(p) != img39.getpixel(p):
            diff += 1
    print(f"\n帧0 vs 帧39: {diff} 像素不同 ({(diff/(W*H))*100:.1f}%)")


        'ESC' ':wq'             #vim
        或
        'ctrl+o'  'ctrl+x'      #nano
退出文本编辑器
 
    python extract_all.py

运行python脚本





