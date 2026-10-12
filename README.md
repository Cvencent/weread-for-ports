# WeRead for Ports / 微信读书 Ports 平台适配方案

> 当前发布：**v10**（2026-10-12），发布说明见 [`docs/release-v10.md`](docs/release-v10.md)。


把微信读书网页版封装成适合 **Ports 掌机**使用的无触屏阅读客户端。项目当前已在
**Powkiddy X35S（640x480、RK3566、1GB 内存）**上完成真机验证，代码结构面向
Ports/EmulationStation 平台，不绑定 X35S，后续可继续适配其他掌机。

> 这不是微信读书官方客户端，也不是对网站的重写。项目通过 Chromium 应用模式、
> 浏览器扩展、手柄映射和启动器，把微信读书网页改造成可用十字键和掌机按键操作的
> Ports 应用。登录、书架、发现和正文分页仍使用微信读书站方页面与账号体系。

## 功能

- 纯手柄操作：书架、发现、阅读、目录、搜索、字号设置和退出均可脱离触屏使用。
- Ports 菜单入口：安装脚本会写入 EmulationStation 的 `Weread.sh` 条目。
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
| 已验证设备 | Powkiddy X35S，640x480，纯手柄 |
| 其他 Ports 掌机 | 架构上可复用，但尚未逐台验证 |
| Chromium | 需要单独安装，仓库不包含约 500MB 的浏览器运行文件 |
| 扩展样式 | 当前只加载 `extension/shell.css` |
| 旧样式 | `extension/legacy/style.css` 仅保留作历史参考，不会被加载 |

## 目录结构

```text
extension/             Chromium MV3 扩展与当前样式
launcher/              掌机启动器、窗口守卫、输入桥、CDP 客户端和 gptokeyb 映射
ports/                 Ports 安装/卸载脚本、gamelist 元数据与封面
docs/                  架构、背景和历史验证记录
tests/                 单元/契约测试、Node 与浏览器测试夹具及真机验收脚本
tools/                 ESLint 配置（测试套件会运行它）
screenshots/           脱敏后的真机界面截图
```

## 安装到 Ports 掌机

### 1. 准备 Chromium

项目的安装脚本会安装微信读书适配文件，但**不会下载 Chromium**，因为运行文件体积
很大。请先把适用于掌机架构的 Chromium 放到：

```text
/storage/roms/ports/browser/chromium/chrome
/storage/roms/ports/browser/nss/
```

启动器要求 `/storage/roms/ports/browser/chromium/chrome` 存在且可执行，并要求
PortMaster 的 `gptokeyb` 可用。不同系统的目录可能不同，可通过环境变量覆盖：

```sh
export WEREAD_BROWSER_DIR=/storage/roms/ports/browser
export WEREAD_EXT_DIR=/storage/.config/weread-ext
```

### 2. 运行安装脚本

把仓库放到掌机可访问的位置后，在仓库根目录执行：

```sh
bash ports/install.sh
```

脚本会：

1. 安装 `Weread.sh` 到 `/storage/roms/ports/`。
2. 安装启动器到 `/storage/roms/ports/weread/`。
3. 安装扩展到 `/storage/.config/weread-ext/`。
4. 安装 `Weread.png` 到 `/storage/roms/ports/media/`。
5. 幂等更新 `/storage/roms/ports/gamelist.xml`，只增加或更新 `./Weread.sh` 条目。
6. 保留已有 Chromium、`gptokeyb` 和 `/storage/.config/weread-profile` 登录资料。

重启 EmulationStation/Ports 前端后，列表中的条目应显示：

- 名称：`微信读书`
- 描述：支持手柄导航、书架与发现、阅读翻页、目录、搜索和字号设置
- 分类：`阅读工具`
- 封面：`./media/Weread.png`

如果系统使用 `essway.service`，在应用文件安装完成后从外部 SSH 重启前端：

```sh
systemctl restart essway.service
systemctl is-active essway.service
```

不要在由 `node.sh` 启动的进程内部停止 `essway.service`；它是启动器的父服务。

### 3. 卸载

```sh
bash ports/uninstall.sh
```

卸载会删除入口、封面、启动器和扩展，但保留登录资料和 Chromium。

## 按键

| 按键 | 操作 |
| --- | --- |
| 十字键 | 浏览页移动焦点；阅读器内翻页 |
| A | 确认、打开书、确认菜单项、输入字母 |
| B | 返回、关闭弹层、退出阅读器 |
| X | 打开目录 |
| Y | 阅读器翻页 |
| L1 / R1 | 上一页 / 下一页；菜单内左右移动 |
| L2 / R2 | 页面顶部 / 底部；阅读器内对应上一页 / 下一页 |
| 左摇杆 | 阅读器内选择正文里的划线评论；上/左选上一条，下/右选下一条，A 打开 |
| START | 打开掌机菜单（目录、设置、搜索、书架、退出） |
| START + SELECT | 同时按住约 1 秒退出应用 |

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

静态检查：

```sh
python -m pyflakes launcher/*.py ports/*.py tests/*.py
npx --yes eslint --config tools/eslint.config.mjs extension/content.js extension/background-v8.1.js
bash -n launcher/node.sh ports/install.sh ports/uninstall.sh ports/Weread.sh
```

真机验收脚本需要 Python、`paramiko` 和可 SSH 连接的掌机。连接信息只通过环境变量提供：

```sh
export WEREAD_HOST=your-device-address
export WEREAD_USER=root
export WEREAD_PASSWORD=your-password
python tests/e2e.py
```

不要把真实地址、密码、登录 Cookie 或个人书架截图提交到仓库。验证记录见
`docs/verification-v9.md`，架构说明见 `docs/architecture.md`。

## 已知限制

- 当前只在 X35S 上完成真机验证；其他 Ports 设备需要确认 Chromium、Wayland/Sway、
  PortMaster、屏幕分辨率和按键映射。
- 首次启动可能较慢，取决于网络和 Chromium 加载速度。
- 搜索键盘输入小写 ASCII/拼音，实际匹配由微信读书决定。
- 正文、目录和字体设置使用站方阅读器，不修改 `.readerChapterContent` 和
  `.preRenderContent` 的分页布局。
- 微信读书是第三方服务，页面结构或接口变化可能影响适配层。
- 仓库不包含 Chromium、登录资料、Cookie、个人书籍数据或截图中的私人内容。

## 许可与归属

本项目只包含掌机适配层。微信读书、Chromium、PortMaster、EmulationStation 及其他
第三方组件的版权和许可归各自权利人所有。
