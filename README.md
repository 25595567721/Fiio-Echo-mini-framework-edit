 
仅用于个人学习，对于Fiio一款ECHO mini播放器固件修改的研究。其中内容大多来自AI，侵权请联系\
如果只想尽快完成修改可直接进入[theme_edit]文件夹，里面含有最新的工具与极简的使用教程\
内容仍会更新\
本项目中研究固件为echo mini v3.9.0 8g版本（HIFIEC39.IMG），其余版本的文件在大多区域类似，哪怕有不同也大概率不会影响到本文所提脚本的使用，但目前并未研究
### 所有涉及图片的脚本在准备图片时都不需要考虑分辨率，脚本会自己调。只需要确保图片比例不要太离谱，因为脚本会强制拉伸图片到320x170
    
    固件命名规则：
    HIFIEC[8G或4G版]/MINIV[512MB版] + 39/390[版本号，此处代指3.9版本]
    前面部分与硬件相关，必须与设备一致    后面数字随便填
    固件拷入播放器后会识别名字，满足要求才会安装

目录文件介绍

    ECHO MINI V3.9.0-----含2026年9月最新固件，可直接在官网下载
    img-out--------------根据内容类别做的固件切分，普通人用不到
    start-frames---------官方镜像的开机动画提取
    theme-edit-----------主题等内容替换脚本，教程在文章最下方，theme_replace.py包含releases中开机动画替换工具所有功能

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

<img width="744" height="345" alt="dms-screenshot-1789908599918" src="https://github.com/user-attachments/assets/5354cf8b-6d94-4e3e-a3f9-b7a50ae56f39" />

G中内容位开机动画
A、B、C、D、E为5套主题文件



<p align="center"># 镜像修改</p>
### 要求
1.已安装python工具

linux安装python 可参考https://geek-blogs.com/blog/install-python-3-12-linux/ \
windows随便找个应用商店吧，我懒得打字<img width="41" height="40" alt="ZZZicon1" src="https://github.com/user-attachments/assets/74a8bcb1-f451-4339-b726-2e357e5e5e36" />



# 开机动画
## 基础信息
屏幕：320×170 横屏\
像素格式：RGB565（2 字节/像素）\
每帧大小：320 × 170 × 2 = 108,800 字节（0x1A900）\



<p align="center">#快速开始</p>
## 1. 提取资源（必做）
python3 theme_extract.py HIFIEC39.IMG
输出：

    theme_dump/ 按主题（G/A/B/C/D/E）分类的 PNG 图片
				manifest.json 资源数据库（替换脚本读取）
    resources.tsv 可检索的文本清单
提取出的内容命名规则（v2.0 关键）：

文件名 = <主题>_<主题内序号>_<名称>.png
同一序号 = 同一角色
     
     A_0012 / B_0012 / C_0012 都是各自主题的"播放背景"

全局区（G）：开机/关机/充电画面（#0~#66）
2. 查找资源
# 列出 A 主题所有资源及序号
python3 theme_replace.py --list A

# 搜索特定名称
grep -i "MUSIC_BACKGROUND" theme_dump/resources.tsv

# 查看 A 主题全屏背景
grep -P "^A\t" theme_dump/resources.tsv | grep "320\t170"
3. 替换资源（生成新固件）
所有模式都会生成 HIFIEC39New.img（若已存在则 HIFIEC39_2_New.img，依此类推），原文件不动。

方式 A：单点替换（按名称）
# 替换 A 主题的播放背景
python3 theme_replace.py HIFIEC39.IMG A:MUSIC_BACKGROUND my_bg.png

# 替换全部 5 套主题中的同名资源
python3 theme_replace.py HIFIEC39.IMG ALL:MUSIC_BACKGROUND my_bg.png

# 通配符匹配
python3 theme_replace.py HIFIEC39.IMG A:MAINMENUPAGE* my_menu.png
方式 B：按序号替换（最可靠）
# 先查序号
python3 theme_replace.py --list A | grep MUSIC_BACKGROUND
# 输出：A  0012  MUSIC_BACKGROUND  320x170  rgb565

# 用全局序号替换
python3 theme_replace.py HIFIEC39.IMG "#79" my_bg.png
方式 C：主题包批量导入（推荐）
准备一个文件夹，放入要替换的图片，文件名带序号：

mkdir mytheme
# 复制几张图进去，命名为：序号.png 或 主题_序号.png
cp theme_dump/A/A_0002_MAINMENUPAGE10.png  mytheme/2.png
cp theme_dump/A/A_0012_MUSIC_BACKGROUND.png mytheme/12.png
cp theme_dump/A/A_0032_BROWSER_BACKGROUND.png mytheme/32.png

# 预览（不写盘）
python3 theme_replace.py mytheme A --dry-run

# 写入（生成 HIFIEC39New.img）
python3 theme_replace.py mytheme A
命名规则：

文件名里第一个数字就是主题内序号（0~309）
支持 2.png、0047.png、A_12.png、frame-92.png 等格式
未提供的序号保留固件原样，不会破坏主题完整性
高级功能：文件名标记（v2.2+）
在文件名里加入标记，实现单图独立控制适配方式、缩放和位移。

1. 适配方式标记（fit）
标记	效果	适用场景
fit1	stretch / 拉伸填满	默认方式，可能变形
fit2	contain / 等比留边	不失真，可能有黑边（颜色可用 --bg 改）
fit3	cover / 等比裁剪	填满不失真，裁掉边缘
示例：

A_12_fit2.png        # 等比缩放，居中留边
2_fit1.png           # 拉伸填满
2. 缩放标记（s/m/l）
标记	倍数	效果
s	0.5×	缩小一半
m	0.75×	缩小 3/4
l	1.25×	放大 1.25 倍
注意：必须作为独立单词（用 _/-/./空格分隔），MUSIC 里的 m 不会误触发。

示例：

A_12_fit2s.png       # 等比留边，再缩到 50%
A_45_fit3l.png       # 等比裁剪，再放大 1.25 倍
3. 位移标记（l/r/u/d + 数字）
标记	方向	像素
l10	左移	10px
r10	右移	10px
u10	上移	10px
d10	下移	10px
也支持全称：left10、right10、up10、down10
可连写：l10u20 = 左移 10 且 上移 20

示例：

A_45_fit3_l10u20.png  # 等比裁剪，1.25 倍，左移 10px 上移 20px
12_u30.png            # 默认适配，上移 30px
4. 组合使用
A_0012_fit2_s_l10.png     # 解析为：序号 12，fit2，0.5 倍，左移 10
0045_battery-fit3-r5.png  # 解析为：序号 45，fit3，右移 5
处理顺序：① 适配到目标尺寸 → ② 中心缩放 → ③ 平移，留白用 --bg 填充

开机动画与关机画面
关机画面（静态，1 张）
全局区 #42（POWEROFF0）：

python3 theme_replace.py HIFIEC39.IMG "#42" my_shutdown.png
开机动画（40 帧）
帧号与资源对应：

帧 0 = G_0000（POWERON0，必须纯黑）
帧 1 = G_0001（POWERON1，必须纯黑）
帧 241 = G_0002G_0041（Z_POWERON0~39，40 帧动画）
方式 A：主题包导入（推荐）

mkdir poweron_theme
cp frames/poweron_00.png poweron_theme/2.png   # 帧 2 = G_0002
cp frames/poweron_01.png poweron_theme/3.png   # 帧 3 = G_0003
...
cp frames/poweron_39.png poweron_theme/41.png  # 帧 41 = G_0041

python3 theme_replace.py poweron_theme G
方式 B：兼容旧版命令

# 替换帧 2~41（等效于 G_0002~G_0041）
python3 theme_replace.py HIFIEC39.IMG mylogo.png 2 41
⚠️ 开机帧特别规则：

帧 0 和帧 1 必须纯黑（0x0000），否则无法开机
如果 40 帧版本刷入失败，先检查这两帧是否被误改
命令参考
全局参数
参数	说明
--fit {stretch,contain,cover}	默认适配方式（默认 stretch）
--bg RRGGBB	留白填充色（默认 000000 黑色）
--dry-run	只预览不写入
--preview [目录]	预览时导出合成后的 PNG（默认 theme_preview/）
--force	强行导入（忽略文件名中的主题字母检查）
-r, --recursive	递归扫描子目录
--firmware <文件>	指定固件（模式三自动识别时用）
--list <主题>	列出该主题的序号表
常用命令速查
需求	命令
提取资源	python3 theme_extract.py HIFIEC39.IMG
只刷新清单（不导图）	python3 theme_extract.py --manifest-only
查 A 主题序号	python3 theme_replace.py --list A
改单张图（按名称）	python3 theme_replace.py echo.img A:MUSIC_BACKGROUND my.png
改全部主题	python3 theme_replace.py echo.img ALL:MUSIC_BACKGROUND my.png
按序号改	python3 theme_replace.py echo.img "#79" my.png
批量导入主题包	python3 theme_replace.py mytheme A
预览不写盘	python3 theme_replace.py mytheme A --dry-run
预览并导出 PNG	python3 theme_replace.py mytheme A --dry-run --preview
改关机画面	python3 theme_replace.py echo.img "#42" my.png
改开机动画（40帧）	python3 theme_replace.py echo.img mylogo.png 2 41
恢复原版	删除生成的 xxxNew.img，原文件未动
实战示例：制作一套深色主题
# 1. 提取
python3 theme_extract.py HIFIEC39.IMG

# 2. 准备资源（从 A 主题复制改造）
mkdir dark_theme
cp theme_dump/A/A_0002_MAINMENUPAGE10.png  dark_theme/2.png
cp theme_dump/A/A_0012_MUSIC_BACKGROUND.png dark_theme/12.png
cp theme_dump/A/A_0032_BROWSER_BACKGROUND.png dark_theme/32.png

# 3. 用 PS/GIMP 改成深色风格，保存回原文件名

# 4. 预览
python3 theme_replace.py dark_theme A --dry-run --preview
# 查看 theme_preview/ 下的合成效果

# 5. 写入 A 主题
python3 theme_replace.py dark_theme A
# 生成 HIFIEC39New.img

# 6. 刷入测试，确认没问题后，同步到其他主题
mkdir dark_theme_all
for f in dark_theme/*.png; do
    num=$(basename "$f" | grep -oP '\d+' | head -1)
    for t in B C D E; do
        cp "$f" "dark_theme_all/${t}_${num}.png"
    done
done

python3 theme_replace.py dark_theme_all B
python3 theme_replace.py dark_theme_all C
python3 theme_replace.py dark_theme_all D
python3 theme_replace.py dark_theme_all E
故障排除
Q: 提示 KeyError: 'local'
A: manifest.json 是旧版。重跑 python3 theme_extract.py --manifest-only，或 v2.3 已自动兼容，忽略警告即可。

Q: 替换后无法开机
A: 检查是否改了 G_0000_POWERON0 或 G_0001_POWERON1，这两帧必须纯黑。删除生成的 xxxNew.img，用原文件重刷。

Q: 图片显示模糊/变形
A: 默认 stretch 会拉伸。小图标（如 19×12 电池）建议按原尺寸作图，或改用 fit2（等比留边）。

Q: 主题包里有的文件没生效
A: 检查文件名里有没有数字，序号是否在 0~309 范围，主题字母是否匹配（A_12.png 只能导入 A 主题，要导入 B 需改名 B_12.png 或加 --force）。

Q: 找不到匹配资源
A: 先跑 python3 theme_extract.py --manifest-only 更新清单，或用 --list 确认名称拼写。

文件说明
文件	说明
HIFIEC39.IMG	原始固件，永不修改
HIFIEC39New.img	第 1 次替换生成的新固件
HIFIEC39_2_New.img	第 2 次替换生成（若 New 已存在）
theme_dump/	提取的资源库
theme_preview/	预览时导出的合成图
manifest.json	资源索引数据库
记住：预览（--dry-run）是个好习惯，特别是批量操作和复杂标记组合时。





















Z_POWERON0 起始位置：BASE + 0x6930 = 0x9BCD12 + 0x6930 = 0x9C4642
