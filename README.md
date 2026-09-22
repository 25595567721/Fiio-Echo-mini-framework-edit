 
仅用于个人学习，对于Fiio一款ECHO mini播放器固件修改的研究。其中内容大多来自AI，侵权请联系\
如果只想尽快完成修改可直接进入看下方[快速开始]，里面介绍最新的工具与极简的使用教程\
内容仍会更新\
本项目中研究固件为echo mini v3.9.0 8g版本（HIFIEC39.IMG），其余版本的文件在大多区域类似，哪怕有不同也大概率不会影响到本文所提脚本的使用，但目前并未研究
### 所有涉及图片的脚本在准备图片要求
### 都不需要考虑分辨率，脚本会自己调。只需要确保图片比例不要太离谱，因为脚本会强制拉伸图片到320x170
### 只支持png和jpg

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



## 5.思路介绍

 FIIO ECHO MINI的交互完全由图片变换完成\
 例如在A主题下在主页时选框向左侧移动是由以下三张图片交替变换\
<img width="320" height="170" alt="0069_MAINMENUPAGE10" src="https://github.com/user-attachments/assets/f49a1bb6-0763-4afb-b172-af46830705f3" />
<img width="320" height="170" alt="0070_MAINMENUPAGE20" src="https://github.com/user-attachments/assets/c56eaf0f-c696-48f2-9a61-0ba60ef77eca" />
<img width="320" height="170" alt="0071_MAINMENUPAGE30" src="https://github.com/user-attachments/assets/fc6713d9-1850-450a-97e7-c52daa7b1b6c" />\
这使得主页主题的动画修改的开放度极其高
    
    举个例子，
    你甚至可以将选框位于文件目录（最左侧）的屏幕显示内容改成一棵树
    也可以将选框位于设置上时的屏幕显示内容改成<浅红法务部合影>，就像下面这个视频

https://github.com/user-attachments/assets/df5270fa-9793-4a41-b6df-37731d840c67

但代价是什么呢，你如果只想做个正儿八经的ui,工作量可能很大\
你可以用ai绘制一套，也可以在网上找别人的图片







# <p align="center">快速开始</p>

	涉及文件均位于[theme_edit]文件夹


# 1. 提取资源（必做）
python3 theme_extract.py HIFIEC39.IMG\
输出：

    theme_dump/ 按主题（G/A/B/C/D/E）分类的 PNG 图片
				manifest.json 资源数据库（替换脚本读取）
    resources.tsv 可检索的文本清单
提取出的内容命名规则（v2.0 关键）：

	文件名 = <主题>_<主题内文件序号>_<资源名>.png
同一序号 = 同一角色
     
     A_0012 / B_0012 / C_0012 都是各自主题的"播放背景"
ABCDE：5个主题区
G：开机/关机/充电画面（#0~#66）


# 2. 查找资源名或序号
## A.文件管理器直接找

建议直接打开文件管理器预览图片确定资源名或序号\
比如你要修改在主界面时，选项位于设置的图片\
你就直接看文件名的资源名和数字序号\
<img width="318" height="278" alt="dms-screenshot-1789984088922" src="https://github.com/user-attachments/assets/999d5965-dfd9-4439-87e4-fc2b8fe408e3" />\
此处数字序号是0002或2，资源名是MAINMENUPAGE10

## B.脚本指令查找

列出 A 主题所有资源及序号
	
	python3 theme_replace.py --list A

搜索特定名称
	
	grep -i "MUSIC_BACKGROUND" theme_dump/resources.tsv

查看 A 主题全屏背景

	grep -P "^A\t" theme_dump/resources.tsv | grep "320\t170"
# 3. 替换资源（生成新固件）
所有模式都会生成 [固件文件名]New.img（若已存在则 [固件文件名]_2_New.img，依此类推），原文件不动。



## 方式 A：按资源名替换

指令格式：
	
	python3 theme_replace.py [固件文件名].IMG [主题]:[资源名] [你的素材图]

 <p align="center"实例</p>

替换 A 主题的播放背景
		
	python3 theme_replace.py [固件文件名].IMG A:MUSIC_BACKGROUND my_bg.png

替换全部 5 套主题中的同名资源

	python3 theme_replace.py [固件文件名].IMG ALL:MUSIC_BACKGROUND my_bg.png

通配符匹配
	
	python3 theme_replace.py HIFIEC39.IMG A:MAINMENUPAGE* my_menu.png


若A方案无法成功，请直接用B方案

## 方式 B：按序号替换（最可靠）


## 方式 B：用全局序号替换

指令格式：

	python3 theme_replace.py [固件文件名].IMG "#序号" [替换用的].png
例如：

	python3 theme_replace.py HIFIEC39.IMG "#79" my_bg.png
	
## 方式 C：主题包批量导入（推荐）

准备一个文件夹，放入要替换的图片，文件名带序号：

	mkdir mytheme   ------创建文件夹，可以直接用图形化软件
	
复制几张图进去，命名为：[序号].png 或 [序号][导入参数].png\


文件名里第一个数字就是主题内序号（0~309）\
支持 2.png、0047.png、A_12.png、frame-92.png 等格式

<img width="663" height="510" alt="dms-screenshot-1789985118002" src="https://github.com/user-attachments/assets/99ef9656-d026-40b3-a477-4af12fa4ffa9" />

未提供的序号保留固件原样，不会破坏主题完整性


*****高级功能*****\
文件名标记来设置导入参数（v2.2+）\
在文件名里加入标记，实现单图独立控制适配方式、缩放和位移。

1. 适配方式标记（fit）

<img width="836" height="216" alt="dms-screenshot-1789985283435" src="https://github.com/user-attachments/assets/8748bfd7-586d-44fd-aa02-1b23942c33c0" />


示例：

	A_12_fit2.png        # 等比缩放，居中留边
	2_fit1.png           # 拉伸填满



2. 缩放标记（s/m/l）

<img width="384" height="205" alt="dms-screenshot-1789985443590" src="https://github.com/user-attachments/assets/e45e288b-fc25-44e9-b316-832f3182995d" />


注意：必须作为独立单词（用 _/-/./空格分隔），MUSIC 里的 m 不会误触发。

	示例：
	A_12_fit2s.png       # 等比留边，再缩到 50%
	A_45_fit3l.png       # 等比裁剪，再放大 1.25 倍


3. 位移标记（l/r/u/d + 数字）

<img width="335" height="267" alt="dms-screenshot-1789985474026" src="https://github.com/user-attachments/assets/66375c77-3b24-4447-96cc-a8250403b4f0" />

也支持全称：left10、right10、up10、down10\
可连写：l10u20 = 左移 10 且 上移 20

	示例：

	A_45_fit3_l10u20.png  # 等比裁剪，1.25 倍，左移 10px 上移 20px
	12_u30.png            # 默认适配，上移 30px

	
4. 组合使用


		A_0012_fit2_s_l10.png     # 解析为：序号 12，fit2，0.5 倍，左移 10
		0045_battery-fit3-r5.png  # 解析为：序号 45，fit3，右移 5

处理顺序：① 适配到目标尺寸 → ② 中心缩放 → ③ 平移，留白用 --bg 填充\








# 关机动画与开机画面
## 关机画面（静态，1 张）
全局区[G] #42（POWEROFF0）：

python3 theme_replace.py HIFIEC39.IMG "#42" my_shutdown.png


## 开机动画
### 基础信息
屏幕：320×170 横屏\
像素格式：RGB565（2 字节/像素）\
每帧大小：320 × 170 × 2 = 108,800 字节（0x1A900）\
未于 G 分区

### 方式 A：主题包导入（推荐）

创建[文件夹]\
在文件夹内放入40张图片\
按照播放次序和序号规则命名图片\
在脚本目录运行

	python3 theme_replace.py [固件文件名.img] [文件夹] G
含义：通过[theme_replace.py]对[固件文件名.img]进行修改，用[文件夹]内与固件内 G 分区序号相同的图片替换原固件内容

### 方式 B：兼容旧版命令

格式：

		python3 theme_replace.py [固件文件名].IMG [你的素材图.png] [起始帧] [结束帧]

实例：\

替换帧 0~39（等效于 G_0000~G_0039）
	
	python3 theme_replace.py HIFIEC39.IMG mylogo.png 0 39
多次运行来替换动画

	python3 theme_replace.py HIFIEC39.IMG mylogo.png 0 5
	python3 theme_replace.py HIFIEC39.IMG mylogo.png 6 19
	python3 theme_replace.py HIFIEC39.IMG mylogo.png 20  21
	.....



# ***theme_replace.py***
# ***命令参考***


全局参数

<img width="970" height="461" alt="dms-screenshot-1789987075147" src="https://github.com/user-attachments/assets/c303155a-1d98-4054-8b90-3f1e2e1ce5d8" />


常用命令速查

<img width="1026" height="644" alt="dms-screenshot-1789987087389" src="https://github.com/user-attachments/assets/9585daed-a31e-42a9-8bb7-12e44d635cfa" />


# 实战示例：制作一套深色主题

以 HIFIEC39.IMG 作为固件
以 dark_theme 作为主题文件夹

## 1. 提取
python3 theme_extract.py HIFIEC39.IMG

## 2. 准备资源

a.网上搜集、ai生成、自己绘制等方式获取图片

b.创建文件夹(可用图形化软件操作)
	
	mkdir dark_theme
c.放入准备的图片并修改为对应序号(可用图形化软件操作)

	cp theme_dump/A/第一张图.png  dark_theme/2.png
	cp theme_dump/A/浅红法务部合影图.png dark_theme/12.png
	cp theme_dump/A/凉吃沙县小吃.png dark_theme/32.png


## 4. 预览(可省略)

	python3 theme_replace.py dark_theme A --dry-run --preview
 查看 theme_preview/ 下的合成效果

## 5. 写入固件并替换原本的 A 主题

	python3 theme_replace.py HIFIEC39.IMG dark_theme A
指令将生成 HIFIEC39New.img，这就是修改后的固件\
原固件并未改动

## 6. 刷入设备

### 故障排除
Q: 提示 KeyError: 'local'\
A: manifest.json 是旧版。重跑 python3 theme_extract.py --manifest-only，或 v2.3 已自动兼容，忽略警告即可。


Q: 图片显示模糊/变形\
A: 默认 stretch 会拉伸。小图标（如 19×12 电池）建议按原尺寸作图，或改用 fit2（等比留边）。

Q: 主题包里有的文件没生效\
A: 检查文件名里有没有数字，序号是否在 0~309 范围，主题字母是否匹配（A_12.png 只能导入 A 主题，要导入 B 需改名 B_12.png 或加 --force）。

Q: 找不到匹配资源\
A: 先跑 python3 theme_extract.py --manifest-only 更新清单，或用 --list 确认名称拼写。

### 文件说明

<img width="667" height="354" alt="dms-screenshot-1789987867890" src="https://github.com/user-attachments/assets/445897e4-685f-4bec-a48f-193d1337016a" />


### 记住：预览（--dry-run）是个好习惯，可以检查将导入的图片的参数是否正确，特别是批量操作和复杂标记组合时很好用。





















Z_POWERON0 起始位置：BASE + 0x6930 = 0x9BCD12 + 0x6930 = 0x9C4642
