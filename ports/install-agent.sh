#!/bin/bash
# ============================================================
#  微信读书掌机版 —— 一条命令安装 / 卸载
#
#  给 AI Agent 或小白用的安装器。整个包自带 Chromium，
#  所以用户不需要另外装任何浏览器。
#
#  安装（复制这一行给 AI Agent 或终端即可）：
#    curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash
#
#  卸载：
#    curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash -s -- --uninstall
#
#  本地已下载了 weread.zip 时：
#    WEREAD_ARCHIVE=/path/to/weread.zip bash install-agent.sh --from-file
# ============================================================
set -euo pipefail

RELEASE_BASE="${WEREAD_RELEASE_BASE:-https://github.com/Cvencent/weread-for-ports/releases/latest/download}"
ARCHIVE_NAME="weread.zip"
PORTS_DIR="${WEREAD_PORTS_DIR:-/storage/roms/ports}"
WEREAD_DIR="$PORTS_DIR/weread"
PROFILE="${WEREAD_PROFILE:-/storage/.config/weread-profile}"
# Scratch space sits beside the ports (the one place we know we can write
# to, since we are about to write the port there) and is deleted after use.
WORK="${WEREAD_WORK:-$PORTS_DIR/.weread-install}"
GAMELIST="${WEREAD_GAMELIST:-1}"

say()  { printf '%s\n' "$*"; }
ok()   { printf '\342\234\205 %s\n' "$*"; }
warn() { printf '\342\232\240\ufe0f  %s\n' "$*" >&2; }
die()  { printf '\342\235\214 %s\n' "$*" >&2; exit 1; }

need_tools() {
  for tool in curl unzip; do
    command -v "$tool" >/dev/null 2>&1 || die "缺少 $tool，无法安装（失败）。"
  done
}

fetch_archive() {
  mkdir -p "$WORK" || die "无法创建临时目录 $WORK（失败）。"
  local archive="$WORK/$ARCHIVE_NAME"

  if [ -n "${WEREAD_ARCHIVE:-}" ]; then
    [ -f "$WEREAD_ARCHIVE" ] || die "找不到本地安装包：$WEREAD_ARCHIVE（失败）。"
    cp -f "$WEREAD_ARCHIVE" "$archive" || die "复制安装包失败（失败）。"
  else
    say "正在下载 $ARCHIVE_NAME ..."
    curl -fL --retry 3 --connect-timeout 30 -o "$archive" \
      "$RELEASE_BASE/$ARCHIVE_NAME" || die "下载失败，请检查网络（失败）。"
  fi

  local sumfile="$WORK/$ARCHIVE_NAME.sha256"
  if [ -z "${WEREAD_ARCHIVE:-}" ]; then
    curl -fL --retry 3 --connect-timeout 30 -o "$sumfile" \
      "$RELEASE_BASE/$ARCHIVE_NAME.sha256" 2>/dev/null || sumfile=""
  elif [ -f "${WEREAD_ARCHIVE}.sha256" ]; then
    cp -f "${WEREAD_ARCHIVE}.sha256" "$sumfile"
  else
    sumfile=""
  fi
  if [ -n "$sumfile" ] && [ -s "$sumfile" ] && command -v sha256sum >/dev/null 2>&1; then
    local expected actual
    expected="$(grep -oE '[0-9a-f]{64}' "$sumfile" | head -n1)"
    actual="$(sha256sum "$archive" | cut -d' ' -f1)"
    [ -n "$expected" ] || die "校验文件里没有 SHA-256（失败）。"
    [ "$expected" = "$actual" ] || die "安装包校验不通过，下载可能损坏（失败）。"
    ok "安装包校验通过"
  else
    warn "没有校验文件，跳过 sha256 校验"
  fi

  printf '%s\n' "$archive"
}

install_port() {
  local archive="$1"
  local staging="$WORK/staging"

  rm -rf "$staging"
  mkdir -p "$staging" || die "无法创建解压目录（失败）。"
  say "正在解压 ..."
  unzip -q -o "$archive" -d "$staging" || die "解压失败，安装包可能损坏（失败）。"

  [ -f "$staging/Weread.sh" ] || die "安装包里没有 Weread.sh（失败）。"
  [ -f "$staging/weread/node.sh" ] || die "安装包里没有 weread/node.sh（失败）。"

  if [ ! -f "$staging/weread/browser/chromium/chrome" ]; then
    die "安装包里没有浏览器（缺少 weread/browser/chromium/chrome），请换用最新版 weread.zip（失败）。"
  fi
  [ -f "$staging/weread/browser/nss/libnss3.so" ] \
    || die "安装包里缺少 nss 库（失败）。"

  mkdir -p "$PORTS_DIR" || die "无法写入 $PORTS_DIR（失败）。"

  rm -rf "$WEREAD_DIR"
  cp -a "$staging/weread" "$WEREAD_DIR" || die "复制端口文件失败（失败）。"
  cp -f "$staging/Weread.sh" "$PORTS_DIR/Weread.sh" || die "复制入口失败（失败）。"

  chmod 755 "$PORTS_DIR/Weread.sh" "$WEREAD_DIR/node.sh" 2>/dev/null || true
  find "$WEREAD_DIR" -type f -name '*.py' -exec chmod 755 {} + 2>/dev/null || true
  find "$WEREAD_DIR/browser" -type f \( -name 'chrome' -o -name '*.so' -o -name '*.so.*' \) \
    -exec chmod 755 {} + 2>/dev/null || true
  find "$WEREAD_DIR/browser/chromium" -maxdepth 1 -type f -name 'chrome*' \
    -exec chmod 755 {} + 2>/dev/null || true

  mkdir -p "$PORTS_DIR/media" 2>/dev/null || true
  if [ -f "$WEREAD_DIR/Weread.png" ]; then
    cp -f "$WEREAD_DIR/Weread.png" "$PORTS_DIR/media/Weread.png" 2>/dev/null || true
  fi

  if [ "$GAMELIST" = 1 ] && [ -f "$WEREAD_DIR/update_gamelist.py" ]; then
    if command -v python3 >/dev/null 2>&1; then
      python3 "$WEREAD_DIR/update_gamelist.py" "$PORTS_DIR/gamelist.xml" \
        --fragment "$WEREAD_DIR/gamelist.fragment.xml" >/dev/null 2>&1 \
        || warn "列表条目写入失败，首次启动时会自动重试"
    fi
  fi

  local bad=0
  [ -x "$PORTS_DIR/Weread.sh" ] || { warn "入口脚本不可执行"; bad=1; }
  [ -f "$WEREAD_DIR/node.sh" ] || { warn "缺少 node.sh"; bad=1; }
  [ -x "$WEREAD_DIR/browser/chromium/chrome" ] || { warn "浏览器不可执行"; bad=1; }
  [ -f "$WEREAD_DIR/ext/content.js" ] || { warn "缺少扩展 content.js"; bad=1; }
  [ "$bad" = 1 ] && die "安装未完成（失败）。"

  rm -rf "$staging"
  rm -rf "$WORK"
  ok "安装完成：$PORTS_DIR/Weread.sh"
  say   "  在掌机前端 ports 里选「微信读书」即可运行。"
  say   "  登录资料保留在 $PROFILE（首次需要手机扫码登录）。"
}

uninstall_port() {
  say "正在卸载 ..."
  if [ "$GAMELIST" = 1 ] && [ -f "$WEREAD_DIR/update_gamelist.py" ] \
     && command -v python3 >/dev/null 2>&1; then
    python3 "$WEREAD_DIR/update_gamelist.py" "$PORTS_DIR/gamelist.xml" --remove \
      >/dev/null 2>&1 || true
  fi
  rm -f "$PORTS_DIR/Weread.sh" "$PORTS_DIR/media/Weread.png"
  rm -rf "$WEREAD_DIR"
  rm -rf "$WORK"
  ok "卸载完成"
  say "  浏览器与登录资料都保留：$PROFILE"
}

usage() {
  cat <<'TXT'
用法：
  install-agent.sh                 下载并安装最新版（自带浏览器）
  install-agent.sh --from-file     用 WEREAD_ARCHIVE 指定的本地 zip 安装
  install-agent.sh --uninstall     卸载（保留登录资料）

可用环境变量：
  WEREAD_PORTS_DIR   端口目录，默认 /storage/roms/ports
  WEREAD_PROFILE     登录资料目录，默认 /storage/.config/weread-profile
  WEREAD_ARCHIVE     本地安装包路径（配合 --from-file）
  WEREAD_GAMELIST=0  不写 gamelist.xml
TXT
}

main() {
  case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    --uninstall) uninstall_port; exit 0 ;;
    --from-file) need_tools; install_port "$(fetch_archive)" ;;
    "") need_tools; install_port "$(fetch_archive)" ;;
    *) usage; die "未知参数：$1（失败）。" ;;
  esac
}

main "$@"
