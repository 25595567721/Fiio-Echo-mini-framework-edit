#!/bin/bash
# 6张图片均匀覆盖全部40帧：每张覆盖6或7帧
IMG="echo.img"
PY="replace_startup.py"
COUNT=6
TOTAL_FRAMES=40
START_FRAME=0

[ -f "$IMG" ] || { echo "错误: 未找到 $IMG"; exit 1; }
[ -f "$PY" ]  || { echo "错误: 未找到 $PY"; exit 1; }

# 选图片目录：png/ 优先，空了用 jpg/
if [ -n "$(find png -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | head -1)" ]; then
    DIR="png"
elif [ -n "$(find jpg -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | head -1)" ]; then
    DIR="jpg"
else
    echo "错误: png/ 和 jpg/ 文件夹中都没有图片"
    exit 1
fi

# 按文件名数字排序
mapfile -t FILES < <(find "$DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null | sort -V)
[ ${#FILES[@]} -lt $COUNT ] && { echo "错误: $DIR/ 中只有 ${#FILES[@]} 张图片，需要 $COUNT 张"; exit 1; }

# 计算均分：每张覆盖 base 帧，前 rem 张多1帧
base=$((TOTAL_FRAMES / COUNT))
rem=$((TOTAL_FRAMES % COUNT))
current=$START_FRAME

echo "使用 $DIR/ 中前 $COUNT 张图片，分布覆盖帧 $START_FRAME~$((START_FRAME+TOTAL_FRAMES-1))"
for ((i=0; i<COUNT; i++)); do
    # 前 rem 张多覆盖 1 帧
    if [ $i -lt $rem ]; then
        len=$((base + 1))
    else
        len=$base
    fi
    end=$((current + len - 1))
    printf "图 %d: 帧 %02d~%02d (%d帧) <- %s\n" $((i+1)) $current $end $len "${FILES[$i]}"
    python3 "$PY" "$IMG" "${FILES[$i]}" "$current" "$end" || { echo "写入失败，已中止"; exit 1; }
    current=$((current + len))
done

echo "✅ 全部完成，共覆盖 40 帧（$base 帧×$((COUNT-rem)) 张 + $((base+1)) 帧×$rem 张）"

