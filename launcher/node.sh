#!/bin/bash
# ============================================================
#  微信读书 掌机版 — 启动器 v8
#
#  ── v6 已解决、v7 保留的坑 ──────────────────────────────
#   · 本脚本由 ES(essway.service) 启动，是它的子进程
#     ⇒ 绝不能 `systemctl stop essway`（= 停自己 → SIGKILL → 黑屏）
#     ⇒ 正确做法：不停 ES，用 swaymsg fullscreen 把窗口盖上
#   · gptokeyb 必须设 SDL_GAMECONTROLLERCONFIG_FILE，否则
#     只有十字键(hat 直通)能用、ABXY/L1R1 全废
#   · 该文件必须指向【ES 那份】db，不是 PortMaster 那份：
#       SDL 权威探针(sdlbind.py)实测结果 ——
#         ES 那份        : a→物理A(0x131),  b→物理B(0x130)   ✅ 正确
#         PortMaster 那份: a→物理B(0x130),  b→物理A(0x131)   ❌ A/B 互反
#
#  ── v7 新增 / 修复 ──────────────────────────────────────
#   1. --remote-debugging-port=9222（仅监听 127.0.0.1）
#      用途：远程读真实 DOM 状态做端到端验证；对正常使用零影响
#   2. 单实例锁 /tmp/weread.lockdir
#      ⚠️ 实测抓到 2 个残留 gptokeyb（各自建了一个 "Fake Keyboard"）
#         ⇒ 同一次物理按键被翻译成两遍键盘事件
#         ⇒ 表现为「按 A 有时进得去、有时没反应」
#      加锁后第二个实例直接退出，从根上杜绝双发
#   3. 强化 cleanup：pidfile + 进程名双清，并校验 /dev/input 无 Fake Keyboard
#   4. 启动前等 sway socket 就绪（最多 15s）
# ============================================================

DEST=/storage/roms/ports/browser
EXT="/storage/.config/weread-ext"
PROFILE=/storage/.config/weread-profile
LOG="$DEST/weread.log"
LOCKDIR=/tmp/weread.lockdir
PIDFILE=/tmp/weread.pid
DEBUG_PORT=9222
WINDOW_GUARD=/storage/roms/ports/weread/window_guard.py
INPUT_BRIDGE=/storage/roms/ports/weread/input_bridge.py
CDP_TOOL=/storage/roms/ports/browser/cdp.py

# ---------------- 单实例锁 ----------------
acquire_lock() {
  local tries=0
  while ! mkdir "$LOCKDIR" 2>/dev/null; do
    local old
    old=$(cat "$LOCKDIR/pid" 2>/dev/null)
    if [ -n "$old" ] && kill -0 "$old" 2>/dev/null; then
      echo "[weread] 已有实例在运行 (pid=$old)，本实例退出"
      exit 0
    fi
    # 陈旧锁：持有者已不在
    rm -rf "$LOCKDIR" 2>/dev/null
    tries=$((tries + 1))
    [ "$tries" -gt 10 ] && { echo "[weread] 无法获取锁"; exit 1; }
  done
  echo $$ > "$LOCKDIR/pid"
}
acquire_lock
echo $$ > "$PIDFILE"

# ---------------- 自检 ----------------
selfcheck() {
  local bad=0
  [ -x "$DEST/chromium/chrome" ] || { echo "❌ chrome 缺失"; bad=1; }
  [ -f "$EXT/content.js" ]       || { echo "❌ 扩展缺失"; bad=1; }
  [ -f "$DEST/weread.gptk" ]     || { echo "❌ 手柄映射缺失"; bad=1; }
  [ -f "$WINDOW_GUARD" ]        || { echo "[weread] window guard missing"; bad=1; }
  [ -f "$INPUT_BRIDGE" ]         || { echo "[weread] input bridge missing"; bad=1; }
  [ -f "$CDP_TOOL" ]              || { echo "[weread] cdp client missing"; bad=1; }
  [ -f "$EXT/background-v8.1.js" ] || { echo "[weread] extension worker missing"; bad=1; }
  [ -f "$EXT/telemetry-rules.json" ] || { echo "[weread] extension rules missing"; bad=1; }
  [ -d "$PROFILE" ]              || mkdir -p "$PROFILE"
  [ "$bad" = 1 ] && return 1
  return 0
}
selfcheck || { sleep 6; exit 1; }

# ---------------- PortMaster 控制环境 ----------------
CF=""
for d in /opt/system/Tools/PortMaster /opt/tools/PortMaster \
         /roms/ports/PortMaster /storage/roms/ports/PortMaster; do
  [ -f "$d/control.txt" ] && { CF="$d"; break; }
done
if [ -n "$CF" ]; then
  # shellcheck source=/dev/null
  source "$CF/control.txt" 2>/dev/null
  get_controls 2>/dev/null
  # ⭐ 覆盖成 ES 那份 db（control.txt 会把它设成 PortMaster 那份，那份 A/B 是反的）
  if [ -f /storage/.config/SDL-GameControllerDB/gamecontrollerdb.txt ]; then
    export SDL_GAMECONTROLLERCONFIG_FILE="/storage/.config/SDL-GameControllerDB/gamecontrollerdb.txt"
  else
    export SDL_GAMECONTROLLERCONFIG_FILE="$CF/gamecontrollerdb.txt"
  fi
fi
GPT="${CF:+$CF/}gptokeyb"
[ -x "$GPT" ] || GPT=/storage/roms/ports/PortMaster/gptokeyb

export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR=/var/run/0-runtime-dir
export LD_LIBRARY_PATH="$DEST/nss:$DEST/chromium:$LD_LIBRARY_PATH"
export MALI_SCHED_RT_THREAD_PRIORITY=95

# sway 控制 socket
for s in /var/run/0-runtime-dir/sway-ipc.0.sock /run/0-runtime-dir/sway-ipc.0.sock; do
  [ -S "$s" ] && { export SWAYSOCK="$s"; break; }
done

# ---------------- 网络守护 ----------------
#  USB 联网钩子(095-usb-net-route)可能删掉 wifi 默认路由且不重建，
#  导致页面打不开（chrome-error://chromewebdata）。这里兜底。
netguard() {
  ip route 2>/dev/null | grep -q "^default .*dev wlan0" && return 0
  local ip4 gw
  ip4=$(ip -4 addr show wlan0 2>/dev/null | awk '/inet /{print $2}' | cut -d/ -f1)
  [ -z "$ip4" ] && return 0
  gw="${ip4%.*}.1"
  ip route add default via "$gw" dev wlan0 metric 100 2>/dev/null
  echo "[weread] netguard: 补回默认路由 via $gw dev wlan0"
}
netguard

# ---------------- 清理 ----------------
kill_hijackers() {
  killall gptokeyb 2>/dev/null
  pkill -f gptokeyb 2>/dev/null
  pkill -f oga_controls 2>/dev/null
  pkill -9 -f gptokeyb 2>/dev/null
  pkill -9 -f oga_controls 2>/dev/null
  sleep 1
}

GPID=""
BPID=""
cleanup() {
  [ -n "$BPID" ] && kill "$BPID" 2>/dev/null
  [ -n "$GPID" ] && kill "$GPID" 2>/dev/null
  kill_hijackers
  pkill -9 -f wvkbd-mobintl 2>/dev/null
  pkill -9 -f "chrome --" 2>/dev/null
  pkill -9 -f "chromium/chrome" 2>/dev/null
  sleep 1
  rm -f "$PROFILE"/Singleton* 2>/dev/null
  rm -rf "$LOCKDIR" 2>/dev/null
  rm -f "$PIDFILE" 2>/dev/null
  # ⚠️ 不停/不启 ES —— ES 一直在跑，只是被 Chrome 盖住；退出后 ES 自然回前台
}
trap cleanup EXIT INT TERM

# ---------------- 启动前清理残留 ----------------
pkill -9 -f "chrome --" 2>/dev/null
kill_hijackers
pkill -f "$INPUT_BRIDGE" 2>/dev/null
rm -f "$PROFILE"/Singleton* 2>/dev/null
sleep 1

# ---------------- 等 sway 就绪 ----------------
for i in $(seq 1 15); do
  [ -n "$SWAYSOCK" ] && [ -S "$SWAYSOCK" ] && break
  sleep 1
done

# ---------------- 手柄映射器 ----------------
"$GPT" -k chrome -c "$DEST/weread.gptk" > "$DEST/gptokeyb.log" 2>&1 &
GPID=$!
sleep 2

# 自检：确保只有【一个】gptokeyb（双实例 = 按键双发）
NG=$(ps -ef | grep -c '[g]ptokeyb')
if [ "$NG" -gt 1 ]; then
  echo "[weread] ⚠️ 检出 $NG 个 gptokeyb，清理后重启"
  kill_hijackers
  "$GPT" -k chrome -c "$DEST/weread.gptk" > "$DEST/gptokeyb.log" 2>&1 &
  GPID=$!
  sleep 2
fi

# ---------------- 浏览器 ----------------
#  ⚠️ 内存：本机仅 976MB RAM（实测 跑一段时间后 available 仅 ~387MB，swap 已用 208MB）
#     ⇒ 必须限制渲染进程数与 JS 堆，否则页面越用越卡、阅读器加载超时。
cd "$DEST/chromium" || exit 1
./chrome \
  --test-type \
  --app="https://weread.qq.com/web/shelf" \
  --no-sandbox \
  --disable-dev-shm-usage \
  --use-gl=angle --use-angle=vulkan \
  --ozone-platform=wayland \
  --enable-features=UseOzonePlatform,Vulkan \
  --ignore-gpu-blocklist \
  --enable-gpu-rasterization \
  --renderer-process-limit=2 \
  --process-per-site \
  --js-flags="--max-old-space-size=256" \
  --disk-cache-size=52428800 \
  --media-cache-size=20971520 \
  --window-size=640,480 --window-position=0,0 \
  --start-fullscreen \
  --no-first-run --no-default-browser-check \
  --disable-features=Translate,CalculateNativeWinOcclusion,MediaRouter,OptimizationHints \
  --disable-background-networking \
  --disable-component-update \
  --remote-debugging-port="$DEBUG_PORT" \
  --disable-extensions-except="$EXT" --load-extension="$EXT" \
  --user-data-dir="$PROFILE" \
  > "$LOG" 2>&1 &
CHPID=$!
python3 "$INPUT_BRIDGE" > "$DEST/input-bridge.log" 2>&1 &
BPID=$!

# ---------------- 等窗口 → 全屏 ----------------
(
  for i in $(seq 1 45); do
    sleep 1
    if [ -n "$SWAYSOCK" ] && python3 "$WINDOW_GUARD" startup; then
      break
    fi
  done
) &

# ---------------- 统一 shell 守卫 ----------------
#  焦点、全屏和异常页兜底合并为一个低频循环：
#   - 不再每 3/4 秒各启动一个 Python/WS 查询；
#   - 页面健康检查异步执行，网络慢时不阻塞焦点/全屏修复；
#   - 保留真正异常页（空/about:blank/chrome-error/chrome://data:）拉回首页。
shell_guard() {
  local tick=0 health_pid=""
  while :; do
    sleep 5
    pgrep -f "chrome --" >/dev/null 2>&1 || break
    tick=$((tick + 1))
    [ -n "$SWAYSOCK" ] || continue
    if [ $((tick % 2)) -eq 0 ]; then
      # One Python start per tick: parse the sway tree once for focus+fullscreen.
      python3 "$WINDOW_GUARD" focus-fullscreen
    else
      python3 "$WINDOW_GUARD" focus
    fi
    if [ $((tick % 4)) -eq 0 ] && [ -z "$health_pid" ]; then
      (
        bad=$(python3 - <<'PY'
import json, urllib.request, sys
try:
    ts = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json", timeout=4))
except Exception:
    sys.exit(0)
for t in ts:
    if t.get("type") != "page":
        continue
    u = (t.get("url") or "").strip()
    if (u == "" or u.startswith("about:blank") or u.startswith("chrome-error")
            or u.startswith("chrome://") or u.startswith("data:")):
        print("BAD")
        break
PY
)
        if [ -n "$bad" ]; then
          echo "[weread] shell guard: 检出异常页面，拉回首页"
          python3 "$CDP_TOOL" --url "https://weread.qq.com/" "location.href" >/dev/null 2>&1
        fi
      ) &
      health_pid=$!
    elif [ -n "$health_pid" ] && ! kill -0 "$health_pid" 2>/dev/null; then
      wait "$health_pid" 2>/dev/null
      health_pid=""
    fi
  done
}
shell_guard &

wait $CHPID
