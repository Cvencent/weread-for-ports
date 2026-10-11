# 微信读书掌机版 · 技术细节与开发指南

> 配套仓库根目录的 `README.md` 使用。本文深入源码机制、部署流程、调试与验证方法。
> 当前验证记录见 `docs/verification-v9.md`。本文中的源码行号和 v6/v7 函数图仅作历史参考；当前视觉样式由 `shell.css` 加载，启动器还依赖 `window_guard.py`。目录和设置通过 `input_bridge.py` 操作；隐藏原生工具栏时不能移除其几何或设为 `display:none`。

---

## 1. `content.js` 内部机制详解（42KB，985 行）

这是一个**单文件 IIFE**（立即执行函数），注入到 `weread.qq.com`。它同时扮演三个角色：**(a)** 手柄按键的页面内翻译层，**(b)** 自绘 UI（导航条/菜单/键盘），**(c)** 焦点管理系统。

### 1.1 关键常量

```js
var FOCUS = 'wr-hh-focus';   // 焦点高亮的 class
var STYLE = 'wr-hh-style';   // 扩展注入的 <style> 的 id
var NAV   = 'wr-hh-nav';     // 顶部导航条容器 id
var MENU  = 'wr-hh-menu';    // 掌机菜单容器 id
var KBD   = 'wr-hh-kbd';     // 屏幕键盘容器 id（注意：非顶层常量，定义在键盘区）
var ROWH  = 28;              // 网格导航的"同一行"判定容差（px）
var TYPE_DELAY = 900;        // 搜索提交前等待 React debounce 的时间
```

### 1.2 核心函数地图（按调用关系）

```
输入层
  document.addEventListener('keydown', ..., true)   ← 捕获阶段！关键
      ├─ SUPPRESS 检查（自己合成的键直接放行）
      ├─ F9 → quitApp()
      ├─ kbdVisible() → kbdMove/runKbd（键盘模式）
      ├─ typing() → 只允许 Escape 逃生
      ├─ menuEl() → 菜单内导航
      ├─ openPanel() → 站方浮层导航
      ├─ isReader() → 翻页/目录/菜单
      └─ 浏览模式 → move/activate/scroll

导航层
  candidates()   ← 收集所有可聚焦元素（含排除逻辑，性能关键）
  move(dir)      ← 方向键移动（含来向记忆）
  recordNav()    ← 写入来向记忆
  focusAt() / focusAtEl() / reanchor() / focusFirst() / anchorFocus()

UI 层
  injectStyle()  ← 注入扩展自己的 CSS（导航条/菜单/键盘样式）
  syncNav()      ← 绘制/更新顶部导航条
  showMenu() / runMenu() / hideMenu() / paintMenu()
  showKbd() / kbdPaint() / runKbd() / hideKbd()
  showHint()     ← 右下角提示气泡

操作层
  activate()     ← 点当前焦点元素（含按钮定位回退）
  turnPage(dir)  ← 翻页（找 pageBtn）
  openCatalog() / openSetting() / openSearch()
  goBack()       ← 三级返回策略
```

### 1.3 焦点系统（本项目最精巧的部分）

**问题**：书架是虚拟滚动网格，DOM 节点会被反复重建；纯索引会错位，纯元素引用会失效。

**方案**：三件套

1. **元素引用** `focusEl` —— 主追踪手段（不用索引，因为索引会因缓存重建而错位）。
2. **身份键** `focusKey` —— 由元素的 `href`/文本/位置算出的稳定 key。元素被销毁后，用 `findByKey()` 找回"同一个逻辑条目"。
3. **500ms 轮询重锚** —— 每 900ms 检查 `focusEl.isConnected`；断连则用 `focusKey` 找回。

**`candidates()` 的排除逻辑**（性能与正确性关键）：
- 排除不可见元素（`shown()` 检查尺寸/display/visibility/opacity）
- 排除**文本输入类**（`isTextish()`）—— 这是 v6 最重要的修复
- 排除父链上已有候选的元素（去重嵌套）
- 导航条的两个 tab 强制插到最前（`tabFirst`）
- 排序：先按 visual row（`rowOf` 用 ROWH 容差），再按 x 坐标

### 1.4 网格导航的可逆性（`move()` + `recordNav()`）

```js
var navFrom = new WeakMap();   // 记「从谁、向哪个方向，到了谁」
function recordNav(from, dir, to) {
  var m = navFrom.get(to) || {};
  m[opposite(dir)] = from;      // 记下反向边，供回退用
  navFrom.set(to, m);
}
```

`move(dir)` 流程：
1. 若当前焦点在记忆里存在 `dir` 方向的来向 → **直接回到那个元素**（保证 ↓↑ 严格对称）。
2. 否则用几何算法（同行找最近、跨行找对齐）选下一个，并 `recordNav()`。

### 1.5 搜索链路（最复杂，涉及跨进程时序）

```
按 START(F10) → showMenu()
  → 选「搜索」→ openSearch()
      → findInput() 找到站方搜索框
      → kbdTarget = 输入框; showKbd()
  → 屏幕键盘：十字键 kbdMove()，A 键 runKbd()
      → typeKey(ch) 用 setNativeValue() 写入（模拟 React 受控组件）
      → 选到 GO → submitSearch()
          → SUPPRESS = true
          → 依次派发 keydown/keypress/keyup (Enter)
          → SUPPRESS = false
          → 延迟 TYPE_DELAY(900ms) 后再 blur
```

**三个必须记住的点**：
1. **`SUPPRESS` 是搜索能工作的唯一原因**。扩展在捕获阶段监听，若不置此标志，自己合成的 Enter 会被自己吞掉，站方 React 永远收不到。
2. **必须延迟 blur**。站方 React 受控组件有 debounce，立刻 blur 会让它处理时拿不到焦点 ⇒ 搜索落空。
3. **`setNativeValue`** 必须用原生 setter 写值，否则 React 的 onChange 不触发。

### 1.6 返回链（`goBack()` 三级策略）

```
① 站方浮层开着 → 派发 Escape 关掉它
② 在阅读器内（isReader() 或 URL 匹配 /web/reader/）→ location.href = '/web/shelf'
   （⚠️ 不用 history.back()，--app 下不可靠）
③ 其他页 → 优先点站内导航链接（SPA 最快）→ 其次 history.back() → 最后 location.href='/'
```

### 1.7 头部注释里的 v6 修复清单（原文保留）

```
1. 【★致命★ 搜索框劫持导航】站方 <input.navBar_input> 被当成普通候选
   ⇒ v6 彻底排除文本输入类元素；搜索改由掌机菜单显式入口
2. 【Escape 被吞】typing() 为真时连 Esc 都吃掉 ⇒ v6 允许 Esc 先 blur 再返回
3. 【候选为空无反馈】⇒ v6 在 diag 里标注 empty 状态，首次按键重试建表
4. 【菜单项增多】加入「搜索」，支持 L1/R1 快速左右移动
5. 【肩键扩展】L1/R1 与 L2/R2 均映射为上一页/下一页；START 统一负责唤出掌机菜单。
```

---

## 2. `node.sh` 内部机制（11KB）

### 2.1 执行顺序

```
acquire_lock()        # mkdir 原子锁；陈旧锁自动清理
  ↓
selfcheck()           # chrome / content.js / weread.gptk 三者必须存在
  ↓
source PortMaster/control.txt + get_controls()   # 拿环境变量
  ↓ 覆盖 SDL_GAMECONTROLLERCONFIG_FILE 为 ES 那份（A/B 才正确）
netguard()            # 若 wlan0 默认路由丢失则补回
  ↓
trap cleanup EXIT INT TERM
  ↓
pkill 残留 chrome + kill_hijackers()
  ↓
等 sway socket 就绪（最多 15s）
  ↓
启动 gptokeyb（-k chrome -c weread.gptk）→ 自检只有 1 个
  ↓
启动 chromium --app=... （见 2.2 参数表）
  ↓
三个后台守卫 + wait $CHPID
```

### 2.2 Chromium 启动参数（每条都有原因）

| 参数 | 作用 |
|---|---|
| `--test-type` | 抑制"正在使用不支持的标志"警告条 |
| `--app="https://weread.qq.com/web/shelf"` | **应用模式**：无地址栏、无标签页，直接进书架 |
| `--no-sandbox` | root 运行必需 |
| `--disable-dev-shm-usage` | 容器/内存受限环境必需 |
| `--use-gl=angle --use-angle=vulkan` | **Mali-G52 硬件加速的关键** |
| `--ozone-platform=wayland` | Wayland 会话必需 |
| `--enable-features=UseOzonePlatform,Vulkan` | 启用上述两特性 |
| `--enable-gpu-rasterization` | GPU 光栅化 |
| `--renderer-process-limit=1` | **内存控制**（976MB 很紧） |
| `--process-per-site` | 减少进程数 |
| `--js-flags="--max-old-space-size=256"` | **限制 JS 堆**，防 OOM |
| `--disk-cache-size=52428800` | 缓存 50MB，防占满 TF 卡 |
| `--window-size=640,480 --window-position=0,0` | 匹配屏幕 |
| `--disable-background-networking` | 省流量/省电 |
| `--remote-debugging-port=9222` | 调试/验证用（仅 127.0.0.1） |
| `--disable-extensions-except=$EXT --load-extension=$EXT` | 加载扩展 |
| `--user-data-dir=$PROFILE` | 登录态持久化 |

### 2.3 三个后台守卫

| 守卫 | 周期 | 职责 | 不做的后果 |
|---|---|---|---|
| `watchdog` | 15s | 检测 page 目标是否为 `about:blank`/`chrome-error`/空 → 拉回首页 | 死页卡住 |
| `focusguard` | 3s | 检测 sway focused 是否还是 chrome，否就抢回 | **手柄全失效**（酷似硬件坏） |
| `fullguard` | 4s | 检测 fullscreen 是否丢失，丢就补 | 视口变 620×339，UI 压扁 |

**⚠️ watchdog 的血泪教训**：早期版本用 `curl /json | grep -q 'chrome://'` 判断异常，但 `/json` 里**始终**有 Omnibox Popup 这类 `chrome://` 目标 ⇒ 模式恒命中 ⇒ **每 15 秒把页面强行拉回首页** ⇒ 用户刚打开书就被踢回。现在只解析 `type=="page"` 的目标。

### 2.4 `cleanup()` 要点

```sh
kill $GPID; kill_hijackers;                    # 杀 gptokeyb
pkill -9 -f "chrome --"; pkill -9 -f "chromium/chrome";
rm -f "$PROFILE"/Singleton*                    # 清 Chrome 单实例锁
rm -rf "$LOCKDIR"; rm -f "$PIDFILE"
# ⚠️ 不停/不启 ES —— ES 一直在跑，只是被 Chrome 盖住；退出后自然回前台
```

---

## 3. 样式与视觉约束

当前扩展只加载 `shell.css`，`extension/legacy/style.css` 仅保留作历史参考。`shell.css` 的样式是**纯视觉**，不参与布局：

1. **网页痕迹清除**：隐藏 `.navBar`/`.shelf_download_app`/`.os-scrollbar`
2. **顶部导航**：`#wr-hh-nav` 渐变底、tab 圆角胶囊
3. **焦点态**：`.wr-hh-focus` 圆角辉光
4. **书架**：暖纸灰底、书封圆角投影
5. **阅读器**：仅 `right:0`（把站方 `right:-80px` 的工具栏拉回屏内）
6. **通用弹层**：圆角
7. **扩展自绘组件**：`#wr-hh-menu`/`#wr-hh-kbd` 圆角

### ⚠️ 三条禁令（写在文件头）

1. **绝不动** `.readerChapterContent` / `.preRenderContent` 的 `width`/`padding`/`font-size`/`line-height`/`letter-spacing`/`text-align`。
2. **`body{background:...}` 会污染阅读器**（阅读器 body 是 `.wr_page_reader`）⇒ 必须限定 `body.wr-hh-has-nav`。
3. 阅读器工具栏**不要加 `overflow:hidden`**（会裁切内部元素）。

### ⚠️ 样式来源有两处（改的时候注意）

- `shell.css` —— `manifest.json` 里实际声明的 CSS
- `content.js` 的 `injectStyle()` —— 扩展运行时注入的基础 CSS

导航条 `#wr-hh-nav` 和菜单 `#wr-hh-menu` 的**基础样式在 `injectStyle()`**，`shell.css` 里的规则负责当前视觉覆盖。改 UI 时两处都要看。

---

## 4. 部署流程（把本地改动推上掌机）

### 4.1 前提

- 掌机与开发机处于同一网络，能够通过 SSH 访问
- 本地有 Python 3；需要设备验收时再安装 `paramiko`，并设置 `WEREAD_HOST`、`WEREAD_PASSWORD` 等环境变量

### 4.2 推送单个文件（推荐用 base64 传输）

使用本仓库的 `ports/install.sh` 安装运行文件；需要单独推送时，请按个人 SSH/SFTP 工具的操作方式连接设备。远端路径以 `/storage` 开头，Windows Git Bash 下要避免路径自动转换。

### 4.3 推送后必须做的事

```sh
# 1. 语法检查（shell 脚本）
bash -n /storage/roms/ports/weread/node.sh

# 2. 冷启动验证（不能只靠热重载）
systemctl stop <你的临时 unit>; killall -q chrome gptokeyb; rm -rf /tmp/weread.lockdir
sleep 3
systemd-run --unit=wr-test --property=BindsTo=essway.service /storage/roms/ports/weread/node.sh &
sleep 20   # 首次加载要 20-30 秒
```

---

## 5. 调试与验证方法论（本项目最有价值的沉淀）

### 5.1 CDP —— 看真实页面状态

```sh
# 在掌机上执行 JS，读真实 DOM
/usr/bin/python3 /storage/roms/ports/browser/cdp.py \
  "(function(){ return JSON.stringify({url:location.href, viewport:innerWidth+'x'+innerHeight}); })()"
```

常用探测：
- 取元素计算样式：`getComputedStyle(document.querySelector('.navBar')).display`
- 取真实坐标：`el.getBoundingClientRect()`
- 翻页判定：`document.querySelector('canvas').toDataURL()` 的哈希

### 5.2 vpad.py —— 注入虚拟手柄（验证输入链路的唯一可靠手段）

```sh
# 在掌机上执行
/usr/bin/python3 /storage/roms/ports/browser/vpad.py down      # 按一次十字键↓
/usr/bin/python3 /storage/roms/ports/browser/vpad.py a         # 按一次 A
/usr/bin/python3 /storage/roms/ports/browser/vpad.py start        # 唤出菜单
```

**为什么必须用它**：它创建一个与真实手柄**同 GUID** 的虚拟手柄，走完整链路
`虚拟手柄 → gptokeyb → Fake Keyboard → Chrome`，所以能验证真实的按键映射。
（`keyinject.py` 直接注入键盘事件，绕过了 gptokeyb，且不可靠。）

**按钮名白名单**（写错会静默失败）：`a b x y l1 r1 l2 r2 select start up down left right`

### 5.3 判定标准（避免假阳性/假阴性）

| 要验证的 | ❌ 错误判据 | ✅ 正确判据 |
|---|---|---|
| 翻页成功 | 看 DOM 文本变化 | 比 `canvas.toDataURL()` 哈希 |
| 搜索成功 | 看 URL 变化 | 查页面文本是否含结果 |
| 手柄链路通 | keyinject 的结果 | vpad.py 的结果 |
| 某样式生效 | 肉眼看/看源码 | `getComputedStyle()` 实读 |
| 某变化是我造成的 | 推测 | **移除样式前后对比**（隔离法） |

### 5.4 标准回归脚本（改完必跑）

```
P1 启动    → 进程数 / 单实例锁 / 落地 URL
P2 视觉    → getComputedStyle 逐项读
P3 开书    → ↓ 移焦点 → A → URL 变 /web/reader/
P4 翻页    → canvas 哈希变化
P5 返回    → B → 回 /web/shelf
P6 菜单    → START → 6 项 → 左右移动 → B 关
P7 搜索    → L2→搜索→逐字母→GO→查结果文本
P8 退出    → START+SELECT → chrome/gptokeyb 归零、ES 仍 active
```

---

## 6. 环境变量与路径速查

```sh
DEST=/storage/roms/ports/browser          # 浏览器与工具
EXT=/storage/.config/weread-ext           # 扩展
PROFILE=/storage/.config/weread-profile   # Chrome 用户数据
LOCKDIR=/tmp/weread.lockdir               # 单实例锁
DEBUG_PORT=9222                           # CDP 端口

export WAYLAND_DISPLAY=wayland-1
export XDG_RUNTIME_DIR=/var/run/0-runtime-dir
export LD_LIBRARY_PATH="$DEST/nss:$DEST/chromium"   # chrome 需要 nss
export SWAYSOCK=/var/run/0-runtime-dir/sway-ipc.0.sock
```

---

## 7. 常见故障速查

| 症状 | 最可能原因 | 处理 |
|---|---|---|
| 按 A 有时灵有时不灵 | 双 gptokeyb 残留 | `killall gptokeyb`，重启应用 |
| 手柄完全没反应（进程都在） | 焦点漂到 ES | focusguard 应自愈；否则 `swaymsg focus` |
| 只有十字键能用，ABXY 全废 | 没设 `SDL_GAMECONTROLLERCONFIG_FILE` | 检查 node.sh 第 79-83 行 |
| UI 被压扁、右边被裁 | 全屏丢失（视口 620×339） | fullguard 应自愈 |
| 白板死页 | 跳了 about:blank（--app 下不退） | watchdog 拉回；检查 quitApp 逻辑 |
| 刚打开书就被踢回首页 | watchdog 误判（`chrome://` 恒命中） | 确认 watchdog 只认 type=="page" |
| 搜索有值但搜不出 | SUPPRESS 未生效 / blur 太早 | 见 1.5 节 |
| 文字重叠错行 | CSS 动了 canvas 容器的布局属性 | 遵守正文布局禁令 |
| 白屏打不开 | wlan0 默认路由丢了 | netguard / 手动 `ip route add` |
| START+SELECT 退不出 | 有别的进程抢了 evdev | `killall gptokeyb oga_controls` |

---

## 8. 源码文件指纹（交接基线）

```
文件                          大小      说明
node.sh                       11117 B   启动器 v7
content.js                    42126 B   交互核心 v6
shell.css                     24515 B   当前视觉样式
manifest.json                   364 B   MV3 清单
weread.gptk                    1198 B   手柄映射 v6
Weread.sh                       112 B   ES 入口
```

> 若你改动后体积/行为与上表差异较大，说明基线已变，请更新本节。

---

*本文档描述的是 2026-10-10 定版的实现。所有机制说明均来自源码与真机实测。*
