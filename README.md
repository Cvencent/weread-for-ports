# WeRead for Ports / 微信读书 Ports 平台适配方案

> 当前发布：**v1.3**（2026-10-23），发布说明见 [`docs/release-v1.3.md`](docs/release-v1.3.md)。
> v1.3 起 **weread.zip 自带 Chromium**，不用再另外装浏览器。


把微信读书网页版封装成适合 **Ports 掌机**使用的无触屏阅读客户端。项目当前已在
**Powkiddy X35S（640x480、RK3566、1GB 内存）**上完成真机验证，代码结构面向
Ports/EmulationStation 平台，不绑定 X35S，后续可继续适配其他掌机。

> 这不是微信读书官方客户端，也不是对网站的重写。项目通过 Chromium 应用模式、
> 浏览器扩展、手柄映射和启动器，把微信读书网页改造成可用十字键和掌机按键操作的
> Ports 应用。登录、书架、发现和正文分页仍使用微信读书站方页面与账号体系。

## 功能

- 纯手柄操作：书架、发现、阅读、目录、搜索、字号设置和退出均可脱离触屏使用。
- PortMaster 原生 port：发布物是标准 `weread.zip`，在 PortMaster 界面里一键安装，
  不需要 SSH，也不需要在掌机上敲任何命令。
- 列表元数据：同时安装中文名称、右侧描述、阅读工具分类和 `640x480` 封面。
- 网格焦点导航：在书架、推荐、榜单和分类页面间移动，并记住来向，方向操作可逆。
- 阅读翻页：支持 L1/R1、方向键和阅读菜单，正文继续使用站方 canvas 分页。
- 站内搜索：掌机自绘屏幕键盘输入拼音，例如 `huozhe`，再提交给站方搜索。
- 登录持久化：账号资料保存在 `/storage/.config/weread-profile`，安装和卸载不会删除。
- 内存控制：限制渲染进程数、JS 堆和磁盘缓存，面向 1GB 内存设备优化。

## 截图

| 分类浏览 | 阅读目录 |
| --- | --- |
| ![分类浏览](screenshots/v9-categories.png) | ![阅读目录](screenshots/v9-catalog.png) |

| 掌机菜单 | 搜索键盘 |
| --- | --- |
| ![掌机菜单](screenshots/v9-menu.png) | ![搜索键盘](screenshots/v9-search-keyboard.png) |

![榜单入口](screenshots/v9-ranks.png)

截图来自真机 640x480 全屏运行，已移除书名、账号和其他私人内容。

## 当前状态

| 项目 | 状态 |
| --- | --- |
| 目标平台 | Ports / EmulationStation |
| 安装方式 | PortMaster 装 `weread.zip`；或一条命令 `install-agent.sh`（给 AI Agent 用） |
| 已验证设备 | Powkiddy X35S，640x480，纯手柄（RK3566 / Mali-G52） |
| 渲染后端 | Mali-G52 硬件渲染（ANGLE / Vulkan），已真机验证 |
| 其他 Ports 掌机 | 架构上可复用，尚未逐台验证；R36S 的差异见下方说明 |
| Chromium | **已打进 `weread.zip`**（Chromium 154.0.8037.97，解压后约 605MB），装完即用 |
| 扩展样式 | 当前只加载 `extension/shell.css` |
| 旧样式 | `extension/legacy/style.css` 仅保留作历史参考，不会被加载 |

## 目录结构

```text
extension/             Chromium MV3 扩展与当前样式
launcher/              掌机启动器、窗口守卫、输入桥、CDP 客户端和 gptokeyb 映射
ports/                 PortMaster 元数据(port.json)、启动器、gamelist 元数据与封面
docs/                  架构、背景和历史验证记录
tests/                 单元/契约测试、Node 与浏览器测试夹具及真机验收脚本
tools/                 ESLint 配置（测试套件会运行它）
screenshots/           脱敏后的真机界面截图
```

## 安装到 Ports 掌机

**结论：只装一个 `weread.zip` 就行，不用装浏览器，不用敲命令。**

下面两条路，选一条。

### 路线 A：一条命令（推荐给 AI Agent / 会用终端的人）

把这一行整行复制给 AI Agent，或者粘到掌机的终端里：

```bash
curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash
```

它会自己完成全部事情：下载 → 校验 SHA-256 → 解压 → 安装 → 自检，最后打印中文结果。
不需要回答任何问题，也不需要提前装 Chromium。

卸载（同样一条命令）：

```bash
curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash -s -- --uninstall
```

### 路线 B：完全不用命令（推荐给纯小白）

**第 1 步**：下载安装包

在电脑浏览器里打开，会自动下载 `weread.zip`（约 194MB）：

```text
https://github.com/Cvencent/weread-for-ports/releases/latest/download/weread.zip
```

**第 2 步**：把这一个文件放进掌机的 autoinstall 目录

把 `weread.zip` 拷到掌机 TF 卡的这个位置（没有这个文件夹就自己新建）：

```text
/storage/roms/ports/PortMaster/autoinstall/
```

**第 3 步**：在掌机上点一下

在掌机前端运行 **PortMaster**，它会弹出 `Auto-installation` 确认框，选 **Install**。

**第 4 步**：完事

回到前端 ports 列表，会多出中文名的「**微信读书**」，点进去就能用。
第一次启动要 20~30 秒（要解压自带的浏览器），属正常。

### 装完是什么样

```text
/storage/roms/ports/
  Weread.sh              ← 前端入口
  weread/                ← 微信读书全部文件（自包含）
    node.sh  window_guard.py  input_bridge.py  cdp.py  weread.gptk
    ext/                 ← 手柄适配扩展
    browser/             ← 自带浏览器（Chromium + NSS + 中文字体）
       MANIFEST.json     ← 每个文件的 SHA-256
```

首次启动会自动做三件幂等的事，都不碰登录资料：

1. 把封面发布到 `/storage/roms/ports/media/Weread.png`；
2. 用 `update_gamelist.py` 写入中文条目「微信读书」；
3. 写 `/storage/.config/fontconfig/conf.d/99-weread-cjk.conf` 注册中文字体。

### 两条命令装不了 / 想省空间？

*已经装过 Browser port* 的人可以改用精简包 `weread-lite.zip`（约 100KB），
它在 PortMaster 里正常安装，但不带浏览器；若 Browser port 不在默认路径，
可以设 `WEREAD_BROWSER_DIR` 指过去。

### 更新 / 卸载

- **更新**：重新装一遍新版 `weread.zip` 即可，整目录替换，登录资料不受影响。
- **卸载**：在 PortMaster 里 Uninstall，或执行 `bash ports/uninstall.sh`。
  两者都只删 `weread/`、`Weread.sh` 和封面，**登录资料与浏览器保留**。

### 备选：SSH 直接从源码装（开发者）

```sh
python tools/build_browser_payload.py   # 先准备自带浏览器（约 500MB）
bash ports/install.sh
```

`install.sh` 落地的是同一套目录，`WEREAD_GAMELIST=0` 可跳过列表编辑。
若系统使用 `essway.service`，装完从外部 SSH 重启前端：

```sh
systemctl restart essway.service
```

不要在由 `node.sh` 启动的进程内部停止 `essway.service`；它是启动器的父服务。

### 附：自己打包（开发者）

改完代码想自己出包：

```sh
python tests/package_portmaster.py     # → output/weread.zip，并按 PortMaster 规则自检
```

打包脚本会复刻 PortMaster `check_port()` 的硬性校验（扁平结构、至少一个顶层目录 +
一个顶层 `.sh`、禁止路径穿越、`port.json` 为 v2），不通过就直接失败——不会产出一个
装不上的包。

## 按键操作

从 EmulationStation 进入：`前端 → ports → 微信读书`。首次启动约 20–30 秒，属正常。

### 总表

| 按键 | 浏览页（书架 / 发现） | 阅读器内 |
| --- | --- | --- |
| 十字键 ↑↓←→ | 移动焦点，长按连发 | 上一页 / 下一页 |
| **A** | 确认、打开书 | 确认；加载失败时重试 |
| **B** | 返回上一层 | 关闭弹层、退出阅读器 |
| **X** | —— | 打开目录 |
| **Y** | —— | 下一页 |
| **L1 / R1** | 上一页 / 下一页；菜单内左右移动 | 同左 |
| **L2 / R2** | 页面顶部 / 底部 | 上一页 / 下一页 |
| 左摇杆 | —— | 选择正文里的划线评论：A 打开 |
| **START** | 唤出掌机菜单 | 唤出掌机菜单 |
| **SELECT** | 退出应用（优先级最高，随时可用） | 同左 |
| **START + SELECT** | 同时按住约 1 秒，退出应用 | 同左 |

> **怎么退出应用**：按 **SELECT**（单独一下即可），或 **START + SELECT** 同时按住约 1 秒。
> 菜单里的「退出」项只会弹出提示、不会真退出——真正的退出键是 SELECT 这两个。
> 退出后回到 EmulationStation，不会黑屏。

### 掌机菜单（按 START）

菜单内容随页面变化，用十字键选择、**A** 确认、**B** 取消：

| 位置 | 菜单项 |
| --- | --- |
| 书架 / 发现 | 搜索 · 书架 · 发现 · 退出 |
| 阅读器内 | 目录 · 阅读设置 · 上一页 · 下一页 · 书架 · 退出 |

### 搜索（掌机没有实体键盘）

1. 按 **START** 唤出菜单，十字键选到「搜索」，按 **A**
2. 底部弹出屏幕键盘：十字键选字母，**A** 输入
   - 直接输入拼音即可，例：`huozhe` → 搜出《活着》
   - 功能键：**删除**（退格）、**清空**（清掉全部输入）、**空格**、**取消**
3. 选到最下方的「搜索」键，按 **A** 提交
4. 按 **B** 可随时关闭键盘

### 提示

- **登录只需一次**（手机扫码），登录态存在本机，之后免登录
- 顶部有「书架 / 发现」标签和搜索按钮，十字键选到后按 **A**
- 切换页面会显示加载状态；等待过久可选「重试」或「返回书架」
- 阅读页右侧工具栏已隐藏，目录与字号改用 **X** 或菜单里的「阅读设置」
- 从「发现」打开的书，按 **B** 会回到原栏目并恢复选中位置

## `gamelist.xml` 说明

仓库提供两个可复用文件：

- `ports/update_gamelist.py`：使用标准库 `xml.etree`，按路径查找并更新条目，
  使用临时文件原子替换，不覆盖其他游戏。解析时保留 XML 注释，因此重新安装
  不会删除你在 `gamelist.xml` 里手写的分组和说明。
- `ports/gamelist.fragment.xml`：包含名称、描述、封面和分类的 `Weread` 条目模板。

也可以单独运行：

```sh
python3 ports/update_gamelist.py /storage/roms/ports/gamelist.xml \
  --fragment ports/gamelist.fragment.xml
```

如果只想移除 `Weread` 条目：

```sh
python3 ports/update_gamelist.py /storage/roms/ports/gamelist.xml --remove
```

## 开发与验证

完整测试套件（静态契约、真实 Chromium 行为、真实 bash 函数、真实 HTTP 端点）：

```sh
python -m unittest discover -s tests -p 'test_*.py'
```

打包成 PortMaster 端口：

```sh
python tests/package_portmaster.py
```

静态检查：

```sh
python -m pyflakes launcher/*.py ports/*.py tests/*.py
npx --yes eslint --config tools/eslint.config.mjs extension/content.js extension/background-v8.1.js
bash -n launcher/node.sh ports/install.sh ports/uninstall.sh ports/Weread.sh
```

真机验收脚本需要 Python、`paramiko` 和可 SSH 连接的掌机。连接信息来自环境变量，
或仓库根目录下 git 忽略的 `.device.env`（`tests/device.py` 会自动读取，真实环境变量优先）：

```sh
# .device.env，一次配好即可；该文件已在 .gitignore 中
WEREAD_HOST=your-device-address
WEREAD_USER=root
WEREAD_PASSWORD=your-password
WEREAD_SSH_PORT=22
```

```sh
python tests/e2e.py
python tests/portmaster_device_acceptance.py
python -m unittest discover -s tests -p "test_discovery.py"
```

`portmaster_device_acceptance.py` 走的是完整闭环：清掉旧安装 → 把 `weread.zip` 放进
`PortMaster/autoinstall/` → 调用设备上 PortMaster 自己的 `harbourmaster` 安装 →
从顶层 `Weread.sh` 启动 → 校验权限、封面发布、gamelist 注册、单实例和登录态保留。

不要把真实地址、密码、登录 Cookie 或个人书架截图提交到仓库；`.device.env` 只留在本地。
验证记录见 `docs/verification-v9.md`，架构说明见 `docs/architecture.md`。

## 设备兼容性

本项目只依赖 Ports/ROCKNIX 生态的四件事：**Sway（Wayland 合成器）**、
**EmulationStation**、**PortMaster**、以及 **640×480 左右的屏幕**。
不依赖 X35S 特有的硬件，所以架构上可以移植到其他掌机。

**但「架构上可用」不等于「装上就能用」。** 目前只有 X35S 做过真机验证。

### 已验证：Powkiddy X35S

| 项目 | 规格 |
| --- | --- |
| SoC / GPU | RK3566，Mali-G52 |
| 分辨率 / 内存 | 640×480，1GB |
| 系统 | ROCKNIX + Sway + EmulationStation + PortMaster |
| 图形加速 | ✅ Mali-G52 硬件渲染（ANGLE / Vulkan），实测证据见下方 |

### 图形加速（实测结论，请先读这段）

在 X35S 上做过一轮逐个后端的真机测试，结论是：**GPU 硬件渲染是真的在跑的**。

**已启用的硬件路径：**

```
--use-gl=angle --use-angle=vulkan
--ozone-platform=wayland
--enable-features=UseOzonePlatform      # 注意：里面不能加 Vulkan
--ignore-gpu-blocklist --enable-gpu-rasterization
```

三条独立证据（均为真机实测）：

| 证据 | 结果 |
| --- | --- |
| `vulkaninfo` | 枚举 `Mali-G52`，`deviceType = INTEGRATED_GPU` |
| 页面 WebGL renderer（CDP `Runtime.evaluate`） | `ANGLE (ARM, Vulkan 1.3.276 (Mali-G52 (0x74021000)), Mali-G52)` |
| GPU 进程已加载的库（`/proc/<gpu-pid>/maps`） | `libmali-vulkan-g52.so`、`libmali-hook.so.1.9.0`、`libgbm.so.1` |

日志里出现的 `swiftshader` 次数为 **0**，也没有任何 `swrast` 回退。

**一个需要注意的表面错误（不影响页面，已修）：**

旧版在 `--enable-features` 里额外带了 `Vulkan`，这会让 Chromium 尝试给
Wayland 合成器建 Vulkan surface，而这条路在本机必然失败：

```
'--ozone-platform=wayland' is not compatible with Vulkan
Failed to create vulkan surface          # 旧版每次启动 6 次
```

把 `Vulkan` 从 `--enable-features` 里删掉后，该错误降到 **1 次**，
而页面 WebGL 依然是同一个 **Mali-G52** 驱动，书架页渲染结果完全一致。
这个修改已随 v1.2 发布，并有回归测试
`tests/test_launcher_gpu_flags.py` 防止它被改回去。

**其他后端的实测结果（都是真实 Wayland 窗口，非 headless）：**

| 后端 | 结果 |
| --- | --- |
| `--use-angle=vulkan` | ✅ Mali-G52（已采用） |
| `--use-angle=gl` / `gles` | ❌ WebGL 直接不可用（headless 下会假性报上 Mali，不可信） |
| `--use-angle=swiftshader` | ⚠️ 纯软渲染 |
| `--use-gl=egl` / `gl`（原生） | ❌ 构建不包含，启动即拒绝 |

**视频硬解（VAAPI）：仍然没有开。** 启动器没有任何
VAAPI flag，设备 `/dev/dri/` 下也只有 `card0`、没有 `renderD*` 节点。
**对本项目无影响**——微信读书是文字阅读器，不播放视频，
硬解对它没有意义。上面说的“硬件加速”指的是
**GPU 渲染加速**，不是视频解码。

### 很可能可用：Game Console R35S / R36S（未实测）

从 ROCKNIX 官方设备文档看，R35S/R36S 满足上面四个依赖：

| 项目 | 规格 | 是否满足依赖 |
| --- | --- | --- |
| 系统 | ROCKNIX（官方支持 RK3326 机型） | ✅ |
| 合成器 | Sway | ✅ |
| 前端 | EmulationStation | ✅ |
| 分辨率 / 内存 | 640×480，1GB | ✅ |
| SoC / GPU | RK3326，Mali-G31 | ⚠️ 见下 |

**实质风险在 GPU 栈。** 启动器把 Chromium 指向
`--use-angle=vulkan`，而这个后端在正确配置下依赖设备提供**真实的 Vulkan
ICD**（硬件驱动）。X35S 上这个 ICD 是
`/usr/share/vulkan/icd.d/mali.json` → `libmali-vulkan-g52.so`，R36S 上是哪个就不一样了。

Mali-G31 上的 Vulkan 支持在 ROCKNIX 上属于**u5b9e验性质**（官方走 libmali
GLES 3.2 + Panfrost GL/GLES 3.1），所以 R36S 上有三种可能结果：

| 情况 | 表现 | 处理 |
| --- | --- | --- |
| ICD 正常 | 与 X35S 一致，Mali-G31 硬件渲染 | 无需处理 |
| ICD 存在但后端不可用 | WebGL 失效，页面保守降级 | 返回下方调试参数 |
| ICD 缺失 | 同上 | 返回下方调试参数 |

**白屏风险很低。** 即使硬件后端完全不可用，Chromium 会回退到
SwiftShader 软渲染——X35S 上我们已经实测过 `--use-angle=swiftshader`，
页面会正常显示（只是慢）。所以真正的风险不是白屏，
而是**变卡**（渲染缓慢）。

如果 R36S 上出现白屏 / 渲染不对，临时验证办法是编辑
`/storage/roms/ports/weread/node.sh`，把 GPU 那两行换成（任选一）：

```sh
--use-angle=swiftshader    # 纯软件渲染，必定能显示，但会慢
--use-gl=angle --use-angle=gl   # 走硬件 GL/GLES（X35S 实测得不到 WebGL，别容易只能补救展示）
```

> 我手上没有 R36S，无法实机验证。如果你在 R36S（或别的掌机）上
> 实测通过，请把结果反馈上来——文档里这行「很可能可用」就可以改成「已验证」。

## 已知限制

- 只在 X35S 上完成真机验证。其他 Ports 设备需自行确认 Chromium、Wayland/Sway、
  PortMaster、屏幕分辨率、按键映射，以及 **GPU 后端是否可用**（见上方设备兼容性）。
- **GPU 渲染已硬件化**（X35S 实测 Mali-G52）；**视频硬解未启用**，但微信读书不播视频，对本项目无影响。
- 首次启动可能较慢，取决于网络和 Chromium 加载速度。
- 搜索键盘输入小写 ASCII/拼音，实际匹配由微信读书决定。
- 正文、目录和字体设置使用站方阅读器，不修改 `.readerChapterContent` 和
  `.preRenderContent` 的分页布局。
- 微信读书是第三方服务，页面结构或接口变化可能影响适配层。
- 仓库不包含 Chromium、登录资料、Cookie、个人书籍数据或截图中的私人内容。

## 许可与归属

本项目只包含掌机适配层。微信读书、Chromium、PortMaster、EmulationStation 及其他
第三方组件的版权和许可归各自权利人所有。
