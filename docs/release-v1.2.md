# WeRead for Ports v1.2 发布说明

发布日期：2026-10-12

## 更正 v1.1 的一处结论：渲染一直跑在 Mali-G52 上

v1.1 的发布说明和 README 里都写了「GPU 加速未真正启用，实际走的是软件路径」。
**这个结论是错的**，这一版把它撤回并附上实测证据。

错在哪：启动器要求 ANGLE 走 Vulkan，同时又在 `--enable-features` 里多传了一个
`Vulkan`。后者会让 Chromium 尝试给 Wayland 合成器建 Vulkan surface，而这条路在
X35S 上必然失败，每次启动刷 6 次：

```text
'--ozone-platform=wayland' is not compatible with Vulkan
Failed to create vulkan surface
```

v1.1 正是看着这些报错，判断渲染掉回了软解。**判断用错了地方**——这些报错只属于
合成器，页面的 WebGL 一直走硬件。

### 实测证据

逐个后端在**真实 Wayland 窗口**下测（不是 headless），用 CDP 读
`WEBGL_debug_renderer_info`：

| 后端 | 真实窗口下的 WebGL renderer |
| --- | --- |
| `--use-angle=vulkan` | `ANGLE (ARM, Vulkan 1.3.276 (Mali-G52 (0x74021000)), Mali-G52)` |
| `--use-angle=gl` / `gles` | 拿不到 WebGL |
| `--use-angle=swiftshader` | 软渲染 |

GPU 进程映射的库（`/proc/<gpu-pid>/maps`）也印证：

```text
libmali-vulkan-g52.so
libmali-hook.so.1.9.0
libgbm.so.1
```

设备上 `vulkaninfo` 直接列出 `Mali-G52`，`deviceType = INTEGRATED_GPU`。

**注意 headless 不可信**：`--use-angle=gl` 和 `gles` 在 headless 下会报出
`Mali-G52`，但真实窗口下它们根本拿不到 WebGL。v1.1 的误判有一部分就来自这里。

## 改动

从 `--enable-features` 里去掉 `Vulkan`：

```diff
-  --enable-features=UseOzonePlatform,Vulkan \
+  --enable-features=UseOzonePlatform \
```

**页面渲染结果一个字节没变**：DOM 464 节点、书本内容正常、WebGL 仍是同一个
Mali-G52 驱动。只是那条刷屏报错从每次启动 6 次降到 1 次。

真机部署后复验：swiftshader 出现 0 次，swrast 回退 0 次。

## 顺带修掉的一个坑

改的过程中在反斜杠续行的参数列表中间写了一行注释。bash 会把 `#` 之后当注释，
**后面所有 flag 被整行吃掉**，应用起不来，报
`--use-gl=angle: command not found`。

`tests/test_launcher_gpu_flags.py` 现在断言参数列表里不能出现注释，防止再犯。

## 测试

- `tests/test_launcher_gpu_flags.py`（4 项）：锁定 vulkan 后端、禁止软件后端、
  禁止 `Vulkan` feature，并检查续行列表里没有注释。
- 全量套件 251 项，其中 6 项 `test_discovery` 失败——这 6 项在本次改动之前就已经
  是红的（把 node.sh 和 README 都 stash 掉后重跑仍然失败），与本次改动无关。

## 视频硬解没有开，也不打算开

VAAPI 相关 flag 一个都没有，设备 `/dev/dri/` 下也只有 `card0`、没有 `renderD*`
节点。微信读书是文字阅读器，不播视频，视频硬解对它没有意义。

上面说的「硬件加速」指的是 **GPU 渲染加速**，不是视频解码。

## 已验证 / 未验证

- **已验证**：Powkiddy X35S（RK3566 / Mali-G52 / 640×480），渲染后端、页面显示、
  退出清理全部真机跑过。
- **未验证**：Game Console R35S / R36S。架构上满足全部依赖，但 GPU 栈不同，
  README 里写清了风险和临时调法。

## 附件

- `weread-for-ports-v12-20261012.zip` —— PortMaster 安装包
- `weread-for-ports-v12-20261012-source.zip` —— 完整源码
- 两个 `.sha256` 校验文件

升级直接覆盖安装即可：登录资料和 Chromium 都不在包里，不会动到已登录的账号。
