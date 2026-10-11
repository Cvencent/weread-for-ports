# WeRead for Ports v10 发布说明

发布日期：2026-10-12

## 重点更新

- 新增独立的 `#wr-hh-busy` 阅读器操作遮罩，不再复用页面导航 Loading。
- 字号切换、字体切换、打开目录、打开设置、关闭面板和打开划线评论都会立即显示对应状态。
- Loading 期间锁住方向键、A/B/X/Y、PageUp/PageDown、Tab、Home/End 等阅读器输入，快速连按会被忽略。
- 完成条件按真实页面状态判断，包括字号等级、字体选中项或样式、目录和设置浮层、评论浮层以及面板关闭。
- 最短显示约 200ms，最长约 5 秒；超时后解除锁定并提示“操作未完成，请重试”。
- 保留原有页面导航 Loading、冷启动重试和返回书架逻辑，避免两套状态互相覆盖。

## 安装包

下载 `weread-for-ports-v10-20261012.zip`，解压后进入 `weread-for-ports-v10-20261012` 目录执行：

```sh
bash ports/install.sh
```

安装脚本会更新：

- `/storage/roms/ports/Weread.sh`
- `/storage/roms/ports/weread/`
- `/storage/.config/weread-ext/`
- `/storage/roms/ports/media/Weread.png`
- `/storage/roms/ports/gamelist.xml` 中的 `./Weread.sh` 条目

已有 Chromium、`gptokeyb` 和 `/storage/.config/weread-profile` 登录资料会被保留。

## 源代码包

`weread-for-ports-v10-20261012-source.zip` 包含完整仓库快照，适合继续开发或审查。解压后可直接运行：

```sh
python -m unittest discover -s ./tests -p 'test_*contract.py' -v
```

## 验证结果

- 静态契约测试：58/58 通过。
- `node --check extension/content.js`：通过。
- 真机 `tests/e2e.py`：通过。
- 真机 `tests/settings_probe.py`：通过。
- 真机专项验证：设置打开、字号连按锁、字体切换、目录、关闭面板、划线评论打开和关闭均正确显示对应 Loading。
- 部署文件通过 SHA256 校验，设备最终停留在书架页，字号和字体已恢复。

## 已知限制

- 当前主要验证设备为 Powkiddy X35S 640×480；其他 Ports 掌机需要确认 Chromium、Wayland/Sway、PortMaster 和按键映射。
- 仓库不包含约 500MB 的 Chromium 运行文件、登录资料或账号 Cookie。
- 首次启动速度取决于网络、Chromium 和微信读书站方资源加载情况。
