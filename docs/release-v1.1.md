# WeRead for Ports v1.1 发布说明

发布日期：2026-10-12

## 修掉的白屏：启动遮罩活过了加载失败的文件

退出微信读书后再点进去，有时会一直白屏，按键完全无效。这是真机才暴露的问题，
静态检查和模拟环境都看不出来。

根因是**启动遮罩和页面本体脱钩**。扩展在 `document_start` 就盖上一个全屏遮罩，
`shell.css` 同时把页面所有元素 `visibility: hidden` 到遮罩消失为止：

```css
html:not(.wr-hh-boot-ready) body > *:not(#wr-hh-boot-mask) { visibility: hidden !important; }
#wr-hh-boot-mask { position: fixed; inset: 0; z-index: 2147483647; background: #f2f4f7; }
```

而遮罩**唯一的**释放点是 `requestAnimationFrame(releaseBootMask)`，它写在 `boot()`
里面，`boot()` 又卡在 `DOMContentLoaded` 上。站方在 `<head>` 里同步加载支付组件
`midas.gtimg.cn`，这个主机一卡住，文档就到不了 `DOMContentLoaded` —— 遮罩挂上了，
释放逻辑永远不会执行。真机上量到该遮罩是 640×480 的不透明覆盖，body 消失时它就是
白屏本身。

原有的 `guardHeadStall` 会重载一次，但每个会话只重载一次，第二次卡住就是死局。

新增 `guardBootMask()` 从三个方向堵住这个缺口：

1. 一旦发现真正的 `body` 就立刻放行，正常路径不再依赖 `boot()` 抢赢慢 head 的竞态；
2. 文档持续卡死时，花**有上限的 3 次**自动重载，瞬时抖动可以自愈；
3. 额度用完后停止自动重载，改由 Enter 键手动重载，用户永远留有一条能走的路。

上限是必须的：对一个永久失效的域名无限重载只会把设备卡在刷新循环里。

### 为什么按 Enter 这条出路真的可用

按键处理原本担心在无 body 状态下收不到输入。真机与 Chromium 上都验证过：
`document` 级 `keydown` 监听器在没有 body 时照常触发，所以这条手动重载是有效的。

### 测试

`tests/test_boot_mask_watchdog.py`（13 项）用真实 Chromium 复现这个坏掉的文档状态。
Chromium 总会自己合成一个 `<body>`，所以测试按解析器崩溃后的样子构造它 —— 文档
还在，但 body 已经没了。把 `guardBootMask` 撤掉后，新测试会以 7 种方式失败，其中包括
白屏那条，确保这个用例真的在盯这个 bug。

## 关于「手柄已连接/已断开连接」刷屏

这个现象曾被观察到，但**不是产品代码的 bug**。

弹窗文案出自 EmulationStation 的翻译表：

```text
msgid "%s connected"    → "%s 已连接"
msgid "%s disconnected" → "%s 已断开连接"
```

`%s` 填的是设备名 `retrogame_joypad`。核实结果是：14 小时内该虚拟手柄被创建了 639
次，峰值每 10 分钟 104 次 —— 来源是验收测试用的 `vpad.py`，它每次调用都建一个虚拟
手柄、发完按键立刻销毁，SDL/ES 监听的是 input 设备热插拔信号，于是每次都被当成一次
真实插拔。产品运行路径从不调用 `vpad.py`，日常使用不会遇到。

配套的 `vpad.py` 已改为设备常驻（守护进程 + unix socket），15 次按键只产生 1 次设备
创建，并附带 `--stop`。同文件里还修掉一个独立缺陷：轴范围被打包进了错误的字段，写出
`minimum=32767 maximum=16` 这种非法区间，即 dmesg 里每次都刷的
`uinput: invalid abs[00] min:32767 max:16`；设备上直接探测 ioctl 确认旧写法返回
`EINVAL`、新写法被内核接受。

该脚本不在本仓库内，属验收工具链，因此不在本次发布物中。

## 打包与测试

- `tests/test_boot_mask_watchdog.py`：13 项，覆盖白屏修复与手动出路的可达性。
- 完整测试套件：`python -m unittest discover -s tests -p "test_*.py"` —— **247 项通过、0 失败**（v1.0 为 234 项）。
- `npx eslint`（`content.js` / `background-v8.1.js`）：0 error（warning 均为既有 `catch (x)` 未使用）。
- `tests/package_portmaster.py`：重新构建并复刻 `check_port()` 的硬性校验通过。

## 验证结果

- **真机部署并校验**：扩展以 sha256 比对确认落地一致，重启后书架正常加载（14 本书）、
  导航渲染、看门狗自检干净（重试额度为 `null`，说明它自动复位且从未触发）。
- **抓到了故障现场**：修复前的实测显示 `hasBody: false`、`scripts: 0`、遮罩仍在，
  而 `headHTML` 有 113KB —— 正是「head 卡住、body 从未创建」的形态。
- **虚拟手柄链路**：15 次按键 → 1 次设备创建，`invalid abs` 错误数保持不变；按 15 次
  `down` 后书架焦点移动到《钟鼓楼》，确认输入链路完好。

## 已知限制

- 沿用 v1.0 的设备与平台范围：主要验证设备为 Powkiddy X35S 640×480。
- 遮罩看门狗的重试上限为 3 次、每次间隔 12 秒；若站方 `<head>` 持续失败，会在约
  36 秒后交由用户手动重载，而不是无限自动刷新。
- `vpad.py` 不在本仓库，设备上 `/storage/roms/ports/browser/vpad.py` 的更新不在版本
  控制范围内，重新部署浏览器目录时需注意。
