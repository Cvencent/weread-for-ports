# v8 UI 重设计与验证

更新日期：2026-10-10（GMT+8）。

## 当前生效的实现

这次针对掌机真实的 640×480、无触屏、全手柄操作重新设计了界面。
保留微信读书的账号、书籍数据和 canvas 阅读引擎，不重新实现正文分页。

- 书架：紧凑导航，四列书籍，首屏完整显示八本书；真实书封和站方原有书籍链接。
- 导航：书架、发现、搜索；书籍选中后用清楚的蓝色描边反馈。
- 发现：压缩搜索区和重复品牌块，继续阅读改为四列；保留站方推荐和书封。
- 菜单：书架显示搜索、书架、发现、退出；阅读显示目录、阅读设置、上一页、下一页、书架、退出。
- 搜索键盘：字母和中文操作键，支持删除、清空、空格、搜索、取消。
- 返回：记住打开的书；返回书架后恢复选中，兼容站方延迟创建/替换书架 DOM。
- 样式：统一在 `shell.css`；`manifest.json` 只加载这一份 CSS，旧 `style.css` 未加载。
- 阅读工具栏：重新定位、压缩间距，所有按钮都在屏幕内，目录与工具栏分开。
- 图标：保留站方矢量资源，缓存路径数据，修复新版发现页缺少 sprite 时的空白按钮。

## 半屏的根因

旧启动器固定匹配 `chrome-weread.qq.com__-Default`，但书架 URL 创建的实际
app ID 为 `chrome-weread.qq.com__web_shelf-Default`。因此全屏和聚焦命令没有
命中窗口，实测浏览器被平铺成 320×480。

新增 `window_guard.py` 递归读取 Sway 树，找到 WeRead 窗口后用实际 `con_id`
执行命令，并读取数字 `fullscreen_mode` 判断是否需要恢复。启动器在启动、
焦点守卫和全屏守卫中调用它。保留 EmulationStation 常驻。

## 修复的交互问题

1. 搜索激活后站方将隐藏导航输入换成可见输入，扩展重新取得当前输入框。
2. 手柄的 keydown 被处理后，对应 keypress/keyup 一并拦截，避免搜索建议收到
   A 或方向键的松开事件，错误替换查询。站方主动合成的提交事件通过 SUPPRESS 放行。
3. 搜索使用屏幕键盘缓冲区提交；B 优先关闭结果浮层，留在原页面。
4. 阅读返回时保留待恢复书籍键，避免 SPA 的延迟加载和定时重新锚定抢走焦点。
5. 站方 `ReaderControls.emitClick` 检查 `event.isTrusted`，普通 `.click()` 不会打开
   目录/设置。扩展 worker 通过只监听 127.0.0.1:9223 的 `input_bridge.py` 请求
   设备已有 CDP 通道发送浏览器输入。服务只接受有限动作名，校验可见、未被遮挡的
   目标；不依赖站方混淆函数或私有 Vue 状态。B 按站方点击面板外的方式关闭。
6. 字号使用滑块实际位置识别当前档位；圆点上的 `.show` 是默认字号提示，
   不能作为当前值。左右方向键逐档调节，字体分类可确认，字体列表在面板内滚动。
7. A 确认前标记当前目标，原生输入完成前暂时拦截重复操作，避免快速接方向键点错章节。
   后台请求设四秒超时，失败后解除输入锁并提示重试。
8. 真机 Chromium 的扩展后台缓存会保留旧脚本，即使更新 manifest 版本并冷启动。
   当前使用新的 `background-v8.1.js` URL；以后修改后台脚本也应更新文件名和 manifest，
   并核对实际运行的 worker 源码，不能仅检查磁盘文件。
9. 字体分类重绘后恢复描边；向上滚动字体列表时避开固定设置栏。字体名称来自
   公开的字体样式，作为稳定的焦点身份，不读取站方私有组件对象。
10. 部分目录晚于点击回调出现，焦点恢复轮询会把焦点移入已加载的面板。
    发现页书卡的内层绝对链接与书架相对链接统一成同一书籍身份，支持返回选中。

## 部署文件

| 本地源码 | 掌机位置 |
|---|---|
| `content.js` | `/storage/.config/weread-ext/content.js` |
| `background-v8.1.js` | `/storage/.config/weread-ext/background-v8.1.js` |
| `shell.css` | `/storage/.config/weread-ext/shell.css` |
| `manifest.json` | `/storage/.config/weread-ext/manifest.json` |
| `node.sh` | `/storage/roms/ports/weread/node.sh` |
| `window_guard.py` | `/storage/roms/ports/weread/window_guard.py` |
| `input_bridge.py` | `/storage/roms/ports/weread/input_bridge.py` |
| `操作说明.txt` | `/storage/roms/ports/browser/操作说明.txt` |

部署脚本：`tests/deploy.py`。先备份，再上传临时文件，运行 Bash
语法检查，原子替换并对照 SHA256，最后冷启动并等待书架就绪。
不删除 `/storage/.config/weread-profile`，不停止 `essway.service`。
输入服务由启动器启动，并在退出时清理。

## 验证记录

以下为 2026-10-10 的实际结果，不沿用旧版的“23 项全通过”。

| 检查 | 结果 |
|---|---|
| 自动回归 | **14 项通过**，90.623 秒；包含窗口选择、真实全屏、两排书架、菜单、搜索事件、延迟返回和响应式边界 |
| 最终冷启动 | Sway 窗口与浏览器 viewport 均为 **640×480**；窗口聚焦，`fullscreen_mode=1`，首屏完整八本书 |
| 其他尺寸 | CDP 模拟 480×360、800×600、1280×720；导航、书卡、菜单和键盘的已测控件边界通过 |
| 实际手柄搜索 | 虚拟手柄 → gptokeyb → 扩展，逐个输入 `huozhe`；查询未被 keyup 改写，提交出结果，B 关闭结果 |
| 正文翻页 | canvas 哈希 **175757588 → 4101160387 → 175757588**；下一页改变正文，上一页恢复原页 |
| 阅读菜单 | 开关菜单前后的正文/预渲染布局相同；未修改阅读引擎的排版参数 |
| 目录 | X 打开；方向键可逆选择；A 原生确认章节，紧接方向键也不会误点下一项；B 关闭目录并留在阅读器 |
| 阅读设置 | 面板边界为左 148、上 8、右 588、下 472；连续调大两档、调小两档恢复，正文随站方字号设置变化 |
| 字体列表 | 分类 A 确认后描边保留；列表上下滚动时焦点不被固定设置栏遮挡；B 关闭，再 B 返回原书 |
| 发现页 | 首屏八本书完整、书封加载成功、顶部搜索图标可见；手柄打开书后返回书架恢复同一本 |
| 全屏恢复 | 主动关闭全屏，观察到 **320×480**，守卫随后恢复 **640×480** |
| 退出清理 | 同时按 START+SELECT；Chrome、gptokeyb、input_bridge 均退出，EmulationStation 保持运行，`essway.service=active` |
| 安装一致性 | 八个运行文件的 SHA256 与交接源码相同；退出测试后重新启动并留在干净的全屏书架 |

完整历史证据文件不随仓库发布；脱敏后的界面截图见 `screenshots/`。其中：

- `v8-regression.log`：完整 14 项测试日志。
- `v8-e2e-evidence.json`：手柄搜索、翻页哈希、目录关闭和返回位置。
- `v8-settings-evidence.json`：字号、分类、滚动及返回。
- `v8-navigation-evidence.json`：原生章节确认、快速按键和发现页。
- `v8-exit-evidence.json`：半屏恢复、退出后进程与 ES 状态。
- `v8-final-state-evidence.json`：最终窗口、八本书和已安装文件 SHA256。

可复现脚本在 `tests/`；当前部署映射以 `tests/deploy.py` 为准。
字体 SVG 项的边界存在不足 1 像素的小数坐标，边界测试采用 1 像素容差，
同时通过 `elementFromPoint` 检查焦点中心确实可见。
完整 `settings_probe.py` 已在最终部署上重跑通过；弹层使用真实可见条件等待，
不依赖固定的短延迟。

## 备份与调试

- 首次改动前的掌机备份：`/storage/.config/weread-ui-backups/20261010-132313`。
- 最后一次部署前备份：`/storage/.config/weread-ui-backups/20261010-152532`。


- 本次临时验收服务：`wr-ui-v8.service`，绑定 `essway.service`；正常入口仍为 ES 的 Weread。
- CDP 仅在设备 localhost:9222；验证手柄使用 `vpad.py`，不使用不可靠的虚拟键盘注入。

## 保留的边界

- 搜索键盘输入字母/拼音，结果匹配由微信读书决定，不保证拼音只对应某一本书。
- 正文、目录和字体设置使用站方阅读器；不改变 `.readerChapterContent`、
  `.preRenderContent` 的宽度、padding、字号、行高、字距或对齐。
- 屏幕“退出”项提示 START+SELECT；实际退出仍由 gptokeyb 处理组合键。
- 网络加载时间、微信读书界面/API 变化、长时间内存占用仍需后续使用观察。
