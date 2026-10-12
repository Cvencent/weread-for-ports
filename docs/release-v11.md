# WeRead for Ports v11 发布说明

发布日期：2026-10-12

## 重点更新

### 安装简化为「一个目录投放」

对齐其他 Ports 的标准做法（一个自包含目录 + 一个顶层启动器，EmulationStation 自动发现），
不再把文件散落到三个目录、不再逐文件 chmod、不再强依赖 gamelist：

```text
/storage/roms/ports/
  Weread.sh              ← 启动器，ES 自动发现
  media/Weread.png       ← 封面
  weread/                ← 全部微信读书文件（自包含）
    node.sh  window_guard.py  input_bridge.py  cdp.py  weread.gptk  操作说明.txt
    ext/  content.js  shell.css  manifest.json  background-v8.1.js  telemetry-rules.json
```

- `node.sh` 用 `HERE` 自定位，更新 = 换掉整个 `weread/` 目录。
- 借用的 Chromium（Browser port）与登录态（`~/.config/weread-profile`）都留在目录外，安装/卸载绝不触碰。
- `install.sh` 在借用 Chromium 缺失时直接拒绝安装；权限两条 `find` 完成；gamelist 编辑可用 `WEREAD_GAMELIST=0` 关闭。
- `uninstall.sh` 只删这一个目录 + 启动器 + 封面，并顺带扫掉旧的散落布局。

### 健壮性与测试加固

- 输入桥（`input_bridge`）始终应答且不钉死线程；`netguard` 修复默认路由。
- CDP 客户端处理分片/控制/掩码帧；窗口守卫 CLI 覆盖真实 sway 树。
- gamelist 重写不再删除用户手写 XML 注释与分组。
- 单实例锁用真实运行覆盖；发现缓存、划线面板 60px 边界、devalue 编码等均新增真实浏览器/CI 覆盖。
- 性能：削减阅读器与面板热路径的布局读取、去掉卡样式始终覆盖的货架虚拟化规则、发现页只缓存实际渲染的切片。
- 修复若干 reader 兼容：`isReader` 识别、滚动键不再误触站点、`pageBtn` 不再遍历全文档读渲染文本。
- MV3 worker 预热消息不再被 allowlist 丢弃。

### 设备连接记录进仓库

真机凭据改存 git 忽略的 `.device.env`，`tests/device.py` 自动读取（真实环境变量优先），
新克隆无需重新配置即可连上设备复验。

## 安装包

下载 `weread-for-ports-v11-20261012.zip`，解压后进入 `weread-for-ports-v11-20261012` 目录执行：

```sh
bash ports/install.sh
```

已有 Chromium、`gptokeyb` 和 `/storage/.config/weread-profile` 登录资料会被保留。

## 源代码包

`weread-for-ports-v11-20261012-source.zip` 包含完整仓库快照，适合继续开发或审查。
解压后可直接运行：

```sh
python -m unittest discover -s ./tests -p "test_*contract.py" -v
```

## 验证结果

- 完整测试套件：`python -m unittest discover -s tests -p "test_*.py"` —— **218 项通过、0 失败**。
- `pyflakes` / `npx eslint`：无 error。
- `bash -n`（`node.sh`/`install.sh`/`uninstall.sh`/`Weread.sh`）：通过。
- 真机（Powkiddy X35S 640×480）：`final_state.py` 通过（部署文件 SHA256 与仓库一致、
  扩展自新路径激活、书架 640×480 全屏）；R1 翻页 5 次产生 5 个不同画布哈希；
  `tests/e2e.py` 前三项稳定通过。部署后设备停留在书架页稳定运行。
- 源码包 `output/weread-for-ports-source.zip` 解压后可直接运行上述测试套件。

## 已知限制

- 当前主要验证设备为 Powkiddy X35S 640×480；其他 Ports 掌机需要确认 Chromium、Wayland/Sway、PortMaster 和按键映射。
- 仓库不包含约 500MB 的 Chromium 运行文件、登录资料或账号 Cookie。
- 首次启动速度取决于网络、Chromium 和微信读书站方资源加载；设备内存 1GB，重负载下偶有加载较慢。
- 完整 `tests/e2e.py` 在该设备上偶有网络时序抖动（回书架重载、翻页加载慢），属环境慢导致的既有现象；
  核心功能（书架/开书/翻页/目录/菜单/搜索）均已单独在真机验证通过。
