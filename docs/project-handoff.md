# 微信读书掌机版 · 项目交接文档

> **当前版本：v10，2026-10-12。请先读 `docs/release-v10.md` 和 `docs/verification-v9.md`。**
> v8 报告与本文后面的 v7/v6 测试表是历史记录，不代表当前验收结果。
> 当前扩展加载 `extension/shell.css`；`extension/legacy/style.css` 是未加载的旧样式。
> 当前启动器使用新增的 `window_guard.py` 匹配实际窗口，修复半屏问题。
> 目录和设置还依赖 `background-v8.1.js` 与本机 `input_bridge.py`，需一起部署。
> 当前运行文件通过 SHA256 对照部署，具体证据和限制见 v9 报告。

---

## 0. 一句话说明这个项目是什么

把**微信读书网页版**改造成一个**掌机专用客户端**（像原生 App 一样），运行在一台没有触屏、没有鼠标、没有键盘、只有 1GB 内存的掌上游戏机上，**全程用手柄操作**，登录用户自己的账号读自己的书。

---

## 1. 目标设备（硬件事实，全部实测）

| 项目 | 参数 |
|---|---|
| 设备 | Powkiddy X35S 掌机 |
| SoC | RK3566，4×Cortex-A55 |
| 内存 | **976 MB**（实测，非常紧张） |
| 屏幕 | 640×480 IPS，**无触屏** |
| GPU | Mali-G52（有 `/dev/mali0`、`/dev/dri/card0`） |
| WiFi | **原机无 WiFi 硬件**，靠外接 USB 网卡（RTL8821CU） |
| 系统 | AURKNIX（ROCKNIX 的下游 fork），`OS_VERSION=20260809` |
| 内核 | 6.18.21 aarch64 |
| 前端 | EmulationStation（`essway.service`，`Restart=always`） |
| 桌面 | sway（Wayland 合成器） |
| Python | 3.13.5，**无 pip**，只有标准库 |
| 存储 | 根文件系统是 **只读 squashfs**；持久化数据必须放 `/storage`（ext4，可写） |
| 浏览器 | 系统**不自带**，本项目外装了 ungoogled-chromium |

### 1.1 关键约束（决定了很多设计）

1. **只读根** ⇒ 任何持久化（扩展、配置、缓存、profile）都必须落在 `/storage`。
2. **无触屏/无鼠标/无实体键盘** ⇒ 所有交互必须能被手柄驱动。
3. **1GB 内存** ⇒ 必须限制 Chrome 渲染进程数与 JS 堆，否则越用越卡。
4. **游戏机定位** ⇒ 前端 ES 常驻，浏览器是"被 ES 启动的一个 port（游戏入口）"。

---

## 2. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  EmulationStation (essway.service，常驻，Restart=always)     │
│    用户从游戏列表选择 "Weread" 入口                            │
└───────────────────────┬─────────────────────────────────────┘
                        │ 启动（作为 ESS 的子进程）
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  /storage/roms/ports/Weread.sh   （3 行的 ES 入口）           │
│      └─> exec /storage/roms/ports/weread/node.sh             │
└───────────────────────┬─────────────────────────────────────┘
                        ▼
┌─────────────────────────────────────────────────────────────┐
│  node.sh  （核心启动器 v8，约 10KB）                          │
│   1. 单实例锁 /tmp/weread.lockdir                            │
│   2. 自检（chrome/扩展/gptk/cdp/worker/rules 是否都在）        │
│   3. netguard（补回被系统钩子删掉的默认路由）                  │
│   4. 启动 gptokeyb（手柄→键盘映射器）                          │
│   5. 启动 chromium --app=...（去地址栏的"应用模式"）           │
│   6. 启动 input_bridge.py（目录 / 设置走真实 CDP 输入）         │
│   7. window_guard.py startup（等窗口并全屏，不停 ES）            │
│   8. shell_guard 循环（focus / focus-fullscreen / 异常页拉回）  │
└───────────┬─────────────────────────────┬───────────────────┘
            │                             │
            ▼                             ▼
┌───────────────────────┐   ┌─────────────────────────────────┐
│  gptokeyb             │   │  Chromium 154.0.8037.97         │
│  weread.gptk 映射表   │   │  --app 模式（无地址栏/无标签页）  │
│  手柄按键→键盘按键      │   │  加载扩展 weread-ext/            │
│  （唯一输入通道）       │   │  CDP 调试端口 9222（仅本机）      │
└───────────────────────┘   └────────────┬────────────────────┘
                                         │
                                         ▼
┌─────────────────────────────────────────────────────────────┐
│  扩展 /storage/.config/weread-ext/   （本项目的核心逻辑）      │
│   ├── manifest.json   （MV3，注入到 weread.qq.com）           │
│   ├── content.js      （42KB，交互核心：导航/菜单/键盘/按键）   │
│   └── shell.css       （当前纯视觉 App 化样式，布局零干预）      │
│                                                             │
│   职责：                                                     │
│   · 手柄→键盘的按键翻译成页面内的"焦点导航"                     │
│   · 自绘顶部导航条（书架/首页）                                │
│   · 自绘掌机菜单（目录/设置/搜索/上一页/书架/退出）              │
│   · 自绘屏幕键盘（无实体键盘也能搜索）                          │
│   · 网格导航算法 + 来向记忆（保证方向键可逆）                    │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 数据流：一次按键的完整旅程

```
用户按手柄 A
  → 内核 /dev/input/event3 产生事件
  → gptokeyb 读取，查 weread.gptk，翻译成 "Enter" 键盘事件
  → gptokeyb 创建一个虚拟键盘设备(Fake Keyboard)，发出 Enter
  → Wayland/sway 把按键投递给当前聚焦窗口（chromium）
  → 站方页面 或 扩展的 content.js 收到 keydown
  → content.js 判断：是菜单/键盘/阅读器/浏览哪种模式？
  → 执行对应动作（移动焦点 / 翻页 / 确认点击）
```

**关键理解**：扩展操控页面**不是**靠"模拟鼠标点击坐标"，而是把**键盘按键翻译成页面内的焦点导航**。因为网页本来就能被键盘操作（Tab/Enter/方向键），扩展负责让手柄按键精准地驱动这套键盘交互。

---

## 3. 文件清单（掌机路径 ↔ 仓库路径）

| 掌机路径 | 仓库路径 | 大小 | 作用 |
|---|---|---|---|
| `/storage/roms/ports/Weread.sh` | `ports/Weread.sh` | 135 B | ES 入口 |
| `/storage/roms/ports/weread/node.sh` | `launcher/node.sh` | 9.8 KB | **核心启动器** |
| `/storage/roms/ports/weread/window_guard.py` | `launcher/window_guard.py` | 2.1 KB | 焦点 / 全屏修复 |
| `/storage/roms/ports/weread/input_bridge.py` | `launcher/input_bridge.py` | 7.1 KB | 阅读器动作 → 真实输入 |
| `/storage/roms/ports/browser/cdp.py` | `launcher/cdp.py` | 5.4 KB | 最小 CDP 客户端（硬依赖） |
| `/storage/.config/weread-ext/content.js` | `extension/content.js` | 103 KB | **交互核心** |
| `/storage/.config/weread-ext/shell.css` | `extension/shell.css` | 27 KB | 当前视觉样式 |
| `/storage/.config/weread-ext/manifest.json` | `extension/manifest.json` | 659 B | 扩展清单 MV3 |
| `/storage/.config/weread-ext/background-v8.1.js` | `extension/background-v8.1.js` | 1.1 KB | MV3 worker（转发 reader-input） |
| `/storage/.config/weread-ext/telemetry-rules.json` | `extension/telemetry-rules.json` | 1.4 KB | 上报屏蔽 / 字体缓存规则 |
| `/storage/roms/ports/browser/weread.gptk` | `launcher/weread.gptk` | 1.4 KB | **手柄映射表** |
| `/storage/roms/ports/browser/操作说明.txt` | `launcher/操作说明.txt` | 1.9 KB | 给用户看的按键表 |




### 3.1 其余运行时文件（不需要交接，仅说明）

- `/storage/roms/ports/browser/chromium/` — Chromium 154 可执行文件（**502 MB**，已做过内核精简）
- `/storage/roms/ports/browser/nss/` — NSS 库（5.3 MB，chromium 依赖）
- `/storage/.config/weread-profile/` — Chrome 用户数据目录（**登录态存这里**，删了要重新扫码）
- `/storage/roms/ports/PortMaster/gptokeyb` — 手柄映射器二进制（118 KB）
- `/storage/roms/ports/browser/weread.log` / `gptokeyb.log` — 运行日志

---

## 4. 历史功能状态（v7 / v6）

下表为上一任开发者记录的 23 项测试，不是本次 v8 验收。新版的实测结果见
`docs/legacy/ui-v8-verification.md`。

| # | 功能 | 状态 |
|---|---|---|
| 1 | 启动进入（ES → ports → Weread） | ✅ |
| 2 | 直接进入书架页（不再停 H5 首页） | ✅ |
| 3 | 登录态持久（只需扫码一次） | ✅ |
| 4 | Mali-G52 硬件加速（`ANGLE (ARM, Vulkan)`） | ✅ |
| 5 | 扩展自动注入 | ✅ |
| 6 | 顶部导航条（书架/首页，A 切换） | ✅ |
| 7 | 十字键网格导航 + **可逆**（↓↑ 精确回原位） | ✅ |
| 8 | A 打开书籍 | ✅ |
| 9 | 阅读器内翻页（L1/R1、方向键） | ✅ |
| 10 | 翻页正确性（canvas 渲染哈希比对） | ✅ |
| 11 | 掌机菜单（START 唤出，6 项） | ✅ |
| 12 | 菜单内 L1/R1 快速左右移动 | ✅ |
| 13 | 屏幕键盘输入（拼音 `huozhe` → 《活着》） | ✅ |
| 14 | 搜索提交（SUPPRESS 旁路放行站方 React） | ✅ |
| 15 | B 返回链（关弹层 → 退阅读器 → 上一层） | ✅ |
| 16 | 目录（X 键） | ✅ |
| 17 | 退出（START+SELECT，进程全清、ES 完好） | ✅ |
| 18 | 单实例锁（防按键双发） | ✅ |
| 19 | shell_guard 焦点自愈（focus / focus-fullscreen） | ✅ |
| 20 | shell_guard 全屏自愈（与焦点合并为一次 sway 查询） | ✅ |
| 21 | shell_guard 死页自愈（异步查 /json，用 cdp.py 拉回） | ✅ |
| 22 | UI App 化视觉（无标题栏/推广条/滚动条） | ✅ |
| 23 | 正文 canvas 分页不受 UI 改动影响 | ✅ |

---

## 5. 手柄按键映射（完整）

映射定义在 `weread.gptk`，含义见下：

| 手柄按键 | 翻译成 | 作用 |
|---|---|---|
| 十字键 ↑↓←→ | ArrowUp/Down/Left/Right（带 repeat 连发） | 书架/首页：移动焦点；阅读器内：翻页 |
| A | Enter | 确定 / 打开书 / 菜单项确认 / 输入字母 |
| B | Escape | 返回 / 关弹层 / 退阅读器 |
| X | Tab | 目录 |
| Y | Space | 翻页 |
| L1 / R1 | PageUp / PageDown | 上一页 / 下一页（菜单内 = 左右移动） |
| L2 / R2 | Home / End | 页面顶部 / 底部（阅读器内 = 上一页 / 下一页） |
| **START** | **F10** | **唤出掌机菜单**（关键，没有它搜索不可达） |
| **START+SELECT** | （gptokeyb 内建） | **退出应用**（唯一真正退出的方式） |

### ⚠️ 关于 START / SELECT 的重要事实

`weread.gptk` 里**故意没有** start/select 条目。原因：
- **START+SELECT 同时按住** 是 gptokeyb 自己内建的"杀进程"组合键，与 gptk 映射表无关，所以退出始终可用。
- 单独按 START 或 SELECT 不做任何事（菜单改用 START 唤出）。

---

## 6. 已踩过的坑（血泪清单，接手必读）

这些坑**每一个都实际发生过**并造成了难查的故障。读这一节能帮你少走几小时的弯路。

### 6.1 进程与启动

**⚠️⚠️ 绝不在从 ES 启动的脚本里执行 `systemctl stop essway`**
`node.sh` 是 `essway.service` 的子进程，停它 = 停自己的父服务 ⇒ 自己也被 SIGKILL ⇒ **黑屏卡死**。
✅ 正确做法：**不停 ES**，用 `swaymsg fullscreen enable` 把浏览器窗口覆盖到 ES 之上。
复现真实场景的测试方法：`systemd-run --unit=t --property=BindsTo=essway.service bash node.sh`（SSH 直接 `nohup` 启动**不是**子进程，测不出这个坑）。

**⚠️⚠️ `gptokeyb` 必须设 `SDL_GAMECONTROLLERCONFIG_FILE`**
不设的话，**只有十字键能用，A/B/X/Y/L1/R1 全部失效**。因为方向键走 hat 直通、按钮走 SDL 名字两条不同路径。
而且该变量必须指向 **ES 那份** db（`/storage/.config/SDL-GameControllerDB/gamecontrollerdb.txt`），**不是** PortMaster 那份——实测两份的 A/B 是**反的**（PortMaster 那份 `a→物理B`、`b→物理A`）。

**⚠️ 输入劫持进程必须成对清理**
`gptokeyb` 用 `EVIOCGRAB` **独占** `/dev/input/event3`。如果它还活着，ES 前端就彻底失去手柄（现象酷似硬件损坏）。
`node.sh` 已用 `trap cleanup EXIT INT TERM` 保证进出都清理。

**⚠️ 双 gptokeyb 导致按键双发**
实测抓到过 2 个残留 gptokeyb，各自创建了一个 `Fake Keyboard`，同一次物理按键被翻译两遍 ⇒ 表现为"按 A 有时灵有时不灵"。已用 `/tmp/weread.lockdir` 单实例锁根治。

### 6.2 Chrome `--app` 模式的行为（反直觉）

**⚠️⚠️ `window.close()` 在 `--app` 模式下无效**（进程不退）。
曾经 `quitApp()` 跳 `about:blank` 想"关闭页面"，结果 `--app` 进程不退 ⇒ **变成白板死页**（进程在、SSH 在、什么都点不动，用户以为崩了）。
✅ 现在 `quitApp()` 只**显示提示**（"请按 START+SELECT"），绝不自杀页面。

**⚠️ `history.back()` 在 `--app` + SPA 下不可靠**（`history.length` 可能为 1）。
✅ 阅读器内返回书架改成直接 `location.href = '/web/shelf'`。

**⚠️ 一段 JS 里做 `location.href` 跳转 ⇒ JS 上下文销毁 ⇒ CDP 的 evaluate 返回 None**。
表现为"测试莫名其妙中断"。✅ 验证时必须 Python 每步独立 evaluate + 每次重新连接 WebSocket。

### 6.3 微信读书网页本身的特性

**⚠️ 正文是 `<canvas>` 绘制的**，DOM 里**文字节点数为 0**。
⇒ 判断"翻页成功"不能看 DOM 文本，必须比对 `canvas.toDataURL()` 的哈希是否变化。

**⚠️⚠️ 站方 JS 会读取容器 computed style 来算分页**。
⇒ **绝不动** `.readerChapterContent` / `.preRenderContent` 的 `width` / `padding` / `font-size` / `line-height` / `letter-spacing` / `text-align`。（仅加 padding 就会导致文字错行重叠。）

**⚠️ 搜索是 SPA 原地渲染，URL 不变**。
⇒ 判断搜索成功不能看 URL，要查页面文本。

**⚠️ 书架是"虚拟滚动网格"**，滚动/重渲染会重建 DOM 节点。
⇒ 用元素引用（而非索引）追踪焦点，并提供"身份键"找回机制。

**⚠️ 站方搜索框 `<input>` 会混进导航候选**，导致 ↓ 跳过第一本书、A 落在空框上。
⇒ 已用 `isTextish()` 彻底排除文本输入类元素。

### 6.4 扩展自身的坑

**⚠️⚠️ 扩展在捕获阶段监听 + `stopPropagation` ⇒ 吞掉站方 React 的 Enter**
这是"搜索框有值但按搜索没反应"的**唯一根因**。
✅ 修法：加 `SUPPRESS` 旁路标志 —— 扩展**自己合成**的按键直接 `return` 放行给站方。

**⚠️⚠️ 纯几何网格导航天然不可逆**。
举例：A、C 在同一行（间距大），B 在下一行 ⇒ `A →↓→ B` 之后，`B →↑→` 会落到 C 而不是 A。
✅ 修法：**来向记忆**（`navFrom` WeakMap，记「从 X 向 dir 到 Y」），命中则精确回退，否则才用几何算法。

**⚠️ SPA 路由切换后必须重新锚定焦点**，否则 `focusEl` 指向已销毁节点 ⇒ 之后所有方向键被当"无焦点"吞掉。

### 6.5 环境与工具

**⚠️ Windows Git Bash 会把 `/storage/...` 转成 Git 安装目录**
⇒ 用 `_push.py` 传远端路径时必须加 `MSYS2_ARG_CONV_EXCL="*" MSYS_NO_PATHCONV=1`，否则"推送成功"但文件落在本地。

**⚠️ busybox 的 `pgrep` 不支持 `-c`** ⇒ 用 `pgrep -f X | wc -l` 计数。

**⚠️ `keyinject.py`（虚拟键盘注入）不可靠**，它测出的失败**全是假失败**（Chrome 常收不到键）。
✅ **验证手柄链路一律用 `vpad.py`**（虚拟手柄，同 GUID，走完整真实链路）。
`vpad.py` 的按钮名**只有**：`a b x y l1 r1 l2 r2 select start up down left right`。写 `enter`/`pagedown` 会**静默失败**。

**⚠️ 虚拟手柄必须完整复制真实手柄的 key 能力集**（本机 **17 个 key code**）。
SDL 的按钮索引 = raw code **升序**排列后的序号，**少注册一个就整体错位**，且表现为"部分按键正常" ⇒ 极易误判成软件 bug。（详见 `vpad.py` 顶部注释。）

---

## 7. 历史 UI 优化建议（v6）

**用户的诉求**：界面要"像原生 App"，不要"像网页"。

**v8 已重新设计书架、导航、菜单和键盘，并统一到 `shell.css`。下面保留旧版设计记录供追溯，勿按旧行号继续修改。**

**已经做过的（v6）**：
- 隐藏了网页标题栏 `.navBar`、App 推广条 `.shelf_download_app`、桌面滚动条 `.os-scrollbar`
- 顶部大 tab 改成 20px 圆角胶囊
- 书封加圆角+投影、底色改暖纸灰 `#f4f2ee`
- 启动 URL 从 `/` 改成 `/web/shelf`（直接进书架）

**还能继续深挖的方向（我认为最有价值的几条）**：

1. **顶部导航条可以彻底重做**。目前 `#wr-hh-nav` 是扩展画的，样式在 `content.js` 的 `injectStyle()` 里用内联字符串定义（约第 82-124 行），和 `shell.css` 里的覆盖规则**两处并存**，改的时候要同时改。建议统一到一处。
2. **书架卡片可以加"App 化"的细节**：阅读进度、封面底部的书名渐变遮罩、卡片按压缩放动效。
3. **可以自绘一个真正的"App 首页"**，完全绕开站方的 H5 首页——比如用扩展拉取书架数据自绘一个 3×2 的封面网格。这是"最像 App"的做法，但工作量最大。
4. **加载态**：目前首次打开有 20-30 秒白屏（站方页面加载 + 我们的登录判断）。可以自绘一个启动 splash。
5. **阅读器顶部/底部栏**：站方的阅读器工具栏比较"网页"，可以重绘成 App 风格（注意：**不能碰 canvas 区域**）。

**⚠️ UI 改动铁律**：
- **只动非 canvas 区域**。任何影响 `.readerChapterContent` / `.preRenderContent` 布局的改动都会破坏分页。
- **`body{background:...}` 会污染阅读器**（阅读器的 body class 是 `wr_page_reader`，要跟随阅读主题切换）。必须限定 `body.wr-hh-has-nav`。
- **改完必须验证 canvas 分页没坏**（比对翻页前后 `canvas.toDataURL()` 哈希）。
- 验证时用「移除样式 → 对比」的隔离法，确认某个视觉变化确实是你造成的，而不是站方默认值。

---

## 8. 如何连接设备、部署、调试

**⚠️ 这一节的操作需要用户配合（涉及内网连接）。** 详细步骤见
`docs/architecture.md` 的“部署流程”和“调试与验证方法论”。
核心要点：
- 掌机与开发机处于同一网络，能够通过 SSH 访问；凭据通过环境变量提供，不写入仓库
- 用 paramiko 做 SSH 客户端（本机已装）；把本地 sh 脚本经 stdin 喂给远端 `sh -s`
- 部署文件用 base64 编码传输（避免引号和二进制问题）
- 调试用 CDP 端口 9222（仅监听 127.0.0.1，需在掌机上本地访问）
- **绝不在掌机上跑 `find /storage`**（116GB exFAT，必然超时）

---

## 9. 待办 / 已知限制

| 项 | 说明 |
|---|---|
| UI 适配 | v8 已重做 640×480 书架、导航、菜单、键盘；后续以新版报告中的实测限制为准 |
| 首次加载 20-30 秒 | 站方页面 + 登录判断耗时，无 splash |
| 无亮度调节 | 硬件层功能，未接入 |
| 搜索仅支持拼音 | 屏幕键盘只注入小写 ASCII，靠站方拼音搜索；不支持手写/语音 |
| 书内文字大小 | 依赖站方设置项，扩展未做快捷调节 |
| 内存紧张 | 976MB，已限制渲染进程数与 JS 堆；长时间使用仍可能变慢 |

---

## 10. 交接开发者的建议工作流

1. **先读懂** `content.js`（交互核心）和 `node.sh`（启动器），这是全部逻辑所在。
2. **改动前先连设备取基线**：用 `cdp.py` dump 当前 DOM 结构和计算样式。**不要凭想象改**。
3. **改 CSS 用"远程注入预览"快速试**：通过 CDP 往页面注入 `<style>` 看效果，满意了再写回文件、推送、冷启动验证。
4. **每次改动后跑一遍关键回归**：开书 → 翻页（哈希） → 返回 → 菜单 → 搜索 → 退出。
5. **验证一律用 `vpad.py`**（手柄链路），不要用 `keyinject.py`。
6. **改 `node.sh` 后必须 `bash -n` 语法检查**，并 `grep` 确认关键行没被 sed 误伤。

---

*本文由项目开发者整理。所有结论均来自真机实测，非推测。如发现文档与设备实际不符，以设备实际为准，并请更新本文档。*
