# WeRead for Ports v12 发布说明

发布日期：2026-10-12

## 重点更新：装法改成真正的「丢个包就完事」

上一版虽然把文件收拢成了一个自包含目录，但装它仍然要 SSH 进掌机敲
`bash ports/install.sh`。这一版把微信读书改成**合规的 PortMaster port**，普通用户在
PortMaster 界面里点一下就装好，全程不碰命令行。

协议不是猜的，是从设备上 PortMaster 自己的源码读出来的
（`pylibs/harbourmaster/{harbour,captain,info}.py`、`control.txt`）：

- **扁平包结构**：`check_port()` 遍历 zip 顶层，要求至少一个顶层目录 + 至少一个顶层
  `.sh`，否则抛 `BadPort` 直接中止；同时禁止 `/` 开头和 `../` 穿越。
- **`port.json` 为 version 2 schema**：`{version, name, items, items_opt, attr:{title,
  desc, inst, genres, porter, image, rtr, exp, runtime, reqs, arch}}`。
- **启动器写法对齐生态**：`Weread.sh` 解析 `controlfolder`、source `control.txt`、
  调 `get_controls`，和 `Browser.sh` / `Celeste.sh` 一致。
- **不需要 install.sh**：首次启动时 `node.sh` 自举，把封面发布到共享
  `ports/media/`，并注册中文 gamelist 条目。

发布物 `weread.zip`（17 个条目，约 98KB）内容：

```text
Weread.sh                       顶层启动器
weread/                         微信读书全部文件（自包含）
  port.json  node.sh  window_guard.py  input_bridge.py  cdp.py  weread.gptk
  Weread.png  update_gamelist.py  gamelist.fragment.xml  操作说明.txt
  ext/  content.js  shell.css  manifest.json  background-v8.1.js
       telemetry-rules.json
```

三条安装路径，装的都是同一个 zip：

1. **autoinstall**：丢进 `/storage/roms/ports/PortMaster/autoinstall/`，下次开
   PortMaster 弹窗确认。
2. **界面从文件安装**：把 zip 拷到 U 盘/共享/下载目录，在 PortMaster 里选它安装。
3. **官方目录**：zip 挂 GitHub Release 并登记进官方端口目录，用户搜「微信读书」直接装。

## 修掉的三个 bug

前两个是**只有真机才暴露**的问题，静态检查和模拟环境都看不出来；第三个是读 PortMaster
源码时发现的协议误解，装在别的架构上才会暴露。

### `set -e` 让启动器在 source 阶段就死掉

`Weread.sh` 原来带 `set -e`。而 PortMaster 的 `control.txt` 里有
`sudo echo "Testing for sudo..."` 这样的探测，本机没装 sudo（返回 127），
脚本在 source 那一刻就退出了，Chromium 根本没起来。生态里 `Browser.sh` /
`Celeste.sh` 都不带 `set -e`，已删除。

### `bootstrap_port` 找错了一层目录

自举代码找的是 `$HERE/../update_gamelist.py`，但包内这些文件就在 `weread/`
（即 `$HERE/`）下。PortMaster 的安装布局下永远找不到 → gamelist 条目从不注册。
已改为 `$HERE/update_gamelist.py` 与 `$HERE/gamelist.fragment.xml`。

### `arch: ["aarch64"]` 会让别的掌机根本搜不到这个 port

这个 port 是 shell + python + JS，借用设备自带的 Chromium，与 CPU 架构无关。原先按惯例
写了 `arch: ["aarch64"]`，但读 `harbourmaster/util.py:551` 的
`match_requirements()` 才发现，PortMaster 会把 `attr.arch` 并进 requirements 并据此
**决定这个 port 是否显示**——架构不匹配的 port 直接从列表里消失。官方目录里现存的
1490 个条目全部是 `arch: []`。已改为 `arch: []`，这样 X35S 以外的 Ports 掌机也能装。

## 打包与测试

- `tests/package_portmaster.py`：构建 `output/weread.zip`，保留 `.sh`/`.py` 的可执行位
  （755），并在打包时**复刻 `check_port()` 的硬性校验**，不合规直接失败——不会产出
  一个装不上的包。
- `tests/test_portmaster_package.py`：16 项测试锁定包结构与启动器契约（扁平布局、
  顶层 `.sh`、无路径穿越、`port.json` v2 字段、权限位、`Weread.sh` 不带 `set -e`、
  不按架构自我屏蔽、自举路径在 `$HERE` 下、SSH 装法与 zip 落地同一棵树等）。
- `tests/portmaster_device_acceptance.py`：真机全流程验收——真的去调设备上
  `harbourmaster` 的 `install_port()`，再从 EmulationStation 启动并核对 Chromium、CDP、
  封面发布、gamelist 注册与登录态。

## 验证结果

- 完整测试套件：`python -m unittest discover -s tests -p "test_*.py"` —— 234 项通过、0 失败。
- `pyflakes`（`launcher/` `ports/` `tests/`）：无输出。
- `npx eslint`（`content.js` / `background-v8.1.js`）：0 error（50 条既有 warning）。
- `bash -n`（`node.sh` / `install.sh` / `uninstall.sh` / `Weread.sh`）：全部通过。
- **真机安装走的是 PortMaster 自己的安装器**：调用设备上 `harbourmaster.HarbourMaster`
  的 `install_port()`，返回 `INSTALL_RC: 0`；落地权限全 755，PortMaster 把
  `port.json` 标记为 `status: Installed`，中文标题 `微信读书` 保留。
- **真机启动走的是 EmulationStation**：从 ES 启动 `Weread.sh` 后 Chromium 起来、
  CDP 9222 起来、封面自动发布到 `media/Weread.png`（41110 字节）、gamelist 自动
  注册（`./Weread.sh` → `微信读书`，带 `./media/Weread.png`）、gptokeyb 单实例 = 1
  （无双发按键），截图确认书架界面正常渲染。
- 已知无害告警一条：PortMaster 提示 `weread/node.sh inside`（建议性提示，非错误）。

## 已知限制

- 当前主要验证设备为 Powkiddy X35S 640×480；其他 Ports 掌机需要确认 Chromium、
  Wayland/Sway、PortMaster 和按键映射。
- 仓库不包含约 500MB 的 Chromium 运行文件、登录资料或账号 Cookie；Chromium 需先由
  Browser port 提供。
- 官方目录那条路径需要把本仓库登记进 PortMaster 的官方端口目录，本仓库只能提供
  zip 与元数据，登记动作由目录维护方完成。
- 首次启动速度取决于网络、Chromium 和微信读书站方资源加载；设备内存 1GB，重负载下
  偶有加载较慢。
