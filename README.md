# Fiio-Echo-mini-framework-edit
    
仅用于个人学习，对于Fiio一款ECHO mini播放器固件修改的研究。其中内容大多来自AI，侵权请联系\
本项目内容目前大多针对linux\
内容仍会更新\
本项目中研究固件为echo mini v3.9.0 8g版本（HIFIEC39.IMG），其余版本的文件在大多区域类似，但目前并未研究
    
    固件命名规则：
    HIFIEC[8G或4G版]/MINIV[512MB版] + 39/390[版本号，此处代指3.9版本]
    前面部分与硬件相关，必须与设备一致    后面数字随便填
    固件拷入播放器后会识别名字，满足要求才会安装
    

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
### 固件动画提取[后面有动画替换教程与工具]
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


### 动画替换
    涉及内容位于/workspaces/Fiio-Echo-mini-framework-edit/startup-change
<p align="center">a.脚本介绍</p>
    
    [Uploading readm# Echo Mini 开机 Logo 替换工具
    replace-startup.py

    用于修改飞傲 Echo Mini（RKNano 平台）固件镜像中的开机动画帧，将原厂 Logo 替换为自定义图片。

    ------------------------------------
    ## ⚠️ 免责声明

    - 本工具仅供个人学习研究

    ## 功能
    - 将任意 PNG/JPG 图片转换为固件使用的 RGB565 像素格式
    - 等长替换开机动画 `Z_POWERON` 序列中的指定帧（不改文件大小、不动索引表）
    - 支持交互式输入和命令行参数两种用法
    - 写入前自动备份固件
    - 写入前校验固件完整性（防止选错文件）


https://github.com/user-attachments/assets/f5662530-6eed-4e36-8956-26319905494d
    
<p align="center">!!图片要求!!</p>

    | 项目 | 说明 |
    |------|------|
    | 尺寸 | 任意尺寸均可，脚本会自动缩放至 **320×170**（设备屏幕分辨率） |
    | 建议 | 直接使用 320×170 的 16:8.5 比例图片，避免缩放变形 |
    | 颜色模式 | 无需带 Alpha 通道（会丢弃） |
    | 格式 | RGB888 → RGB565 转换过程中会损失少量色阶精度（正常现象，渐变可能有轻微色带） |


<p align="center">!!环境要求!!</p>

    ```bash
    pip install pillow
    ```

    - Python 3.6+
    - 支持的图片格式：PNG、JPG、BMP 等 Pillow 可识别的格式

    - 安卓手机可用普通python编译器运行


 <p align="center">工作原理</p>

    ```
    固件镜像 (HIFIEC39.IMG)
    └── 0x9BCD12: ROCK26IMAGERES 资源区
        ├── 索引表: [宽:4B][高:4B][数据长度:4B][数据偏移:4B] × N
        └── 0x6930 处: Z_POWERON0 像素数据
            └── 每帧 320×170×2 = 108,800 字节 (RGB565 LE)
                共 40 帧连续排列
    ```

    替换方式为**等长覆盖**：
    1. 图片 → RGB565 字节流（恰好 108,800 字节/帧）
    2. 按 `0x9BCD12 + 0x6930 + 帧号 × 108800` 定位
    3. 逐帧写入，不改文件总大小、不影响校验逻辑
        因此可以多次运行脚本
        如第一次运行修改1-6帧，第二次6-9,以此类推
        最终文件保存到当前目录下[固件文件名].IMG


<p align="center">!!使用方法!!</p>

    将脚本放在固件镜像同目录下运行。

    ### 交互式（推荐新手）

    ```bash
    python replace_logo.py
    ```

    按提示依次输入即可，都有默认值：
    [效果展示]
        ```
        固件镜像文件名 [HIFIEC39.IMG]:
          ✓ 固件: HIFIEC39.IMG (32.0 MB)
        Logo 图片文件名: mylogo.png
        替换起始帧 (Logo渐显建议从2开始) [2]:
        替换结束帧 (建议6) [6]:
        ```

    ### 命令行

    ```bash
    python replace_logo.py <固件文件> <Logo图片> <起始帧> <结束帧>
        注：logo图片可写绝对地址或相对地址，若在同一目录可直接写文件名

    # 示例
    python replace_logo.py HIFIEC39.IMG mylogo.png 2 6
    ```


<p align="center">帧选择指南</p>

    经过差分分析，V3.9.0 固件的 40 帧开机动画分为几个阶段：

    | 阶段 | 帧号 | 内容 | 建议 |
    |------|------|------|------|
    | 黑屏 | 0–1 | 无画面 | 不用改 |
    | **Logo 渐显** | **2–6** | 原厂 Logo 从小到大渐入 | **主战场，替换这5帧** |
    | 稳定显示 | 7–29 | Logo 稳定 + 微动效 | 可改可不改 |
    | 场景切换 | 30–33 | 大幅画面变化 | 按需 |
    | 静止 | 34–38 | 无变化 | 不用改 |
    | 结束 | 39 | 过渡到主界面 | 可按 Logo 替换 |

    **入门建议**：第一次只替换帧 2~6（默认参数），观察效果后再决定是否替换更多帧。

    **最小改动验证**：第一次刷机前，建议先只替换 1 帧（如 `python replace_logo.py HIFIEC39.IMG mylogo.png 2 2`），确认设备能接受修改后的固件且启动正常，再进行大规模修改。





<p align="center">!!文件说明!!</p>

    运行后会生成：

    ```
    固件文件名.IMG          # 修改后的固件（直接刷入使用）
    固件文件名.IMG.backup   # 自动备份（首次运行时创建，之后跳过）
    ```

<p align="center">常见问题</p>

    **Q: 刷入后 Logo 颜色偏色/花屏？**
    A: 本固件为小端 RGB565，脚本已按此处理。若出现颜色异常，请确认修改的是正确的帧号，且图片本身是正常显示的。

    **Q: 提示"文件太小"？**
    A: 选错文件了，固件镜像应为 32 MB（33,554,432 字节）的 `HIFIEC39.IMG`。

    **Q: 刷入后设备无法开机？**
    A: 用备份固件重刷恢复。若备份也被覆盖，重新从飞傲官网下载对应版本固件。部分设备有按键组合强刷模式，可查官方文档。

    **Q: 可以改关机画面 / UI 界面吗？**
    A: 可以。同一资源区内还有 `POWEROFF0`（关机画面）、`MAINMENUPAGE10~50`（主菜单）、`MUSIC_BACKGROUND`（播放界面）等资源，结构和开机帧完全相同，改脚本中的帧定位参数即可。不同主题的同类资源带 `B`/`C_`/`D_`/`E_` 前缀。

<p align="center">固件兼容性</p>

    - 分析基于 **V3.9.0 (HIFIEC39.IMG)**，偏移地址写死在该版本
    - 其他版本固件偏移可能不同，需重新分析后修改脚本中的 `BASE` 和 `FRAME_START_ABS`
    - 不同固件版本可能有版本号校验（固件内含 `Max_version 4120` 检查），建议保留原版本字段


b.脚本内容

[replace_startup.py](https://github.com/user-attachments/files/32429658/replace_startup.py)

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
  c.命令行成品脚本
        
        分为6、14、27、40
    
内含b.中[replacce_startup.py]与shell脚本replace_().sh\
运行shell脚本后，shell脚本会自动识别当前目录内的[replacce_startup.py]、图片文件夹[png/jpg]、名为[echo.img]的镜像文件\
在对应文件夹内的png或jpg文件夹放入图片并按数字大小排序（数字可以不连续，不从1开始）\
需将固件更名为echo.img.\
在脚本运行完后将echo.img改回原文件名，如HIFIEC39.img
    
    [40的不知道为什么，如果第一张不是纯黑就没成功烧录，所以我就内置了01，这样就保证了第一张一定是黑色，而且如果你的图   片里有1.png/jpg也可以正常使用]







