#!/bin/bash
# 27张图片均匀覆盖全部40帧：前13张各2帧，后14张各1帧
IMG="echo.img"
PY="replace_startup.py"
COUNT=27
TOTAL_FRAMES=40
START_FRAME=0

[ -f "$IMG" ] || { echo "错误: 未找到 $IMG"; exit 1; }
[ -f "$PY" ]  || { echo "错误: 未找到 $PY"; exit 1; }

if [ -n "$(find png -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | head -1)" ]; then
    DIR="png"
elif [ -n "$(find jpg -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) 2>/dev/null | head -1)" ]; then
    DIR="jpg"
else
    echo "错误: png/ 和 jpg/ 文件夹中都没有图片"
    exit 1
fi

mapfile -t FILES < <(find "$DIR" -maxdepth 1 -type f \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" \) 2>/dev/null | sort -V)
[ ${#FILES[@]} -lt $COUNT ] && { echo "错误: $DIR/ 中只有 ${#FILES[@]} 张图片，需要 $COUNT 张"; exit 1; }

base=$((TOTAL_FRAMES / COUNT))
rem=$((TOTAL_FRAMES % COUNT))
current=$START_FRAME

echo "使用 $DIR/ 中前 $COUNT 张图片，分布覆盖帧 $START_FRAME~$((START_FRAME+TOTAL_FRAMES-1))"
for ((i=0; i<COUNT; i++)); do
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

