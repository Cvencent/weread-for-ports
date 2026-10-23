# WeRead for Ports v1.3 发布说明

发布日期：2026-10-23

## 这一版就干一件事：一个小白只装一个包

之前的 `weread.zip` 只有 98KB，因为它**借用** Browser port 的 Chromium
（约 500MB，还要用户在 PortMaster 里另外装一遍）。对小白的实际体验是：

1. 装 Browser port；
2. 装 weread.zip；
3. 如果 Browser port 装到了别的路径，还得自己设 `WEREAD_BROWSER_DIR`；
4. 中文字体还得另外铺一层 fontconfig 配置，否则满屏方块。

**这一版把浏览器、NSS 库和中文字体全部打进 `weread.zip`**，装完即用，不需要再装
任何浏览器，也不需要手写任何配置。

## 改动

### 1. 包内自带 Chromium 154

`weread.zip` 现在带 `weread/browser/`：

```text
weread/browser/
├── chromium/           Chromium 154.0.8037.97（ungoogled-chromium arm64 便携版）
├── nss/                12 个 NSS/NSPR 库（Debian arm64 提取）
├── fonts/              NotoSansSC-Regular.otf（中文字体）
└── MANIFEST.json       每个文件的 SHA-256，装机后可校验
```

体积：解压后约 605MB，打包后 194.4MB（已去掉 326 个用不到的语言包、
chromedriver 和 crashpad handler，省下约 240MB）。

启动器现在默认在**自己旁边**找浏览器：

```bash
BROWSER_DIR="${WEREAD_BROWSER_DIR:-$HERE/browser}"
```

想继续用共享 Browser port 的老用户，设 `WEREAD_BROWSER_DIR` 覆盖即可，行为不变。

### 2. 中文字体自动注册

系统字体里没有 CJK 字形。启动器首次运行时写
`/storage/.config/fontconfig/conf.d/99-weread-cjk.conf`，把包内的
Noto Sans SC 接进 fontconfig。

**用 `conf.d/` 而不是改写 `fonts.conf`**：fontconfig 自动读取 `conf.d/*.conf`，
所以其他程序/其他 port 已有的字体配置不会被覆盖。任何一步失败都不影响启动。

### 3. 可执行位自动补齐

PortMaster 用 Python 的 `zipfile` 解压，**不会还原 unix 权限**；而它只在 ext4 上统一
`chmod 777`（X35S 的 ports 在 exFAT 上，这一步直接跳过）。结果是装完 `chrome`
可能是 644，启动即失败。

启动器现在自己补：`ensure_browser_exec()` 发现 `chrome` 没有可执行位就 `chmod 755`，
顺带补 `nss/` 和 `chromium/` 下的 `.so`。只读文件系统也不会卡住启动。

### 4. 浏览器缺失时报中文可行动提示

以前缺 Chromium 只有一行英文 `❌ chrome 缺失`，小白看不出要做什么。现在直接告诉他
查的是哪个路径、重装哪个包：

```text
❌ 浏览器缺失：没找到 /storage/roms/ports/weread/browser/chromium/chrome（重新安装 weread.zip 即可）
```

### 5. 一条命令给 AI Agent 用

新增 `install-agent.sh`，可以整行丢给 AI Agent 或终端：

```bash
curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash
```

它自己下载、校验 SHA-256、解压、装好、自检，最后打印中文结果。卸载：

```bash
curl -fsSL https://github.com/Cvencent/weread-for-ports/releases/latest/download/install-agent.sh | bash -s -- --uninstall
```

脚本**全程无交互**（Agent 答不了 `read -p` 的提问），并且**永远不碰登录资料目录**
`/storage/.config/weread-profile`。

### 6. 两个包，按需选

| 文件 | 大小 | 适合谁 |
| --- | --- | --- |
| `weread.zip` | 194.4MB（下载） | **所有人**。自带浏览器，装完即用 |
| `weread-lite.zip` | 约 100KB | 已经装了 Browser port、想省空间的人 |

`weread-lite.zip` 需要在 PortMaster 里另外装 Browser port，并可用
`WEREAD_BROWSER_DIR` 指定它的位置。

## 稳定的下载来源

包内浏览器来自这两个固定地址，构建脚本按 SHA-256 校验：

| 内容 | 来源 | SHA-256 |
| --- | --- | --- |
| Chromium 154 arm64 | `ungoogled-software/ungoogled-chromium-portablelinux` release `154.0.8037.97-1` | `594c337b…ef4a09f1` |
| libnspr4 | `deb.debian.org` 4.35-1 | `3aa6bc5a…982ae28d` |
| libnss3 | `security.debian.org` 3.87.1-1+deb12u4 | `aaa1b291…22b2b6d0` |

重打包（需要先下载那 134MB 的 tarball）：

```bash
python tools/build_browser_payload.py     # → output/browser_payload/
python tests/package_portmaster.py        # → output/weread.zip
python tests/verify_release_zip.py        # 解包后逐文件校验
```

体积大 + 带宽是关键，所以 CI（`.github/workflows/release.yml`）负责在打 tag 时重新
构建并发布这两个包和 `install-agent.sh`。

## PortMaster 的权限坑（记录一下，别再踩）

PortMaster 的安装流程（`harbourmaster/hm_install.py`）只做两件事：解压 + 按
`port.json` 的 `items` 填 `gamelist`/权限。它**没有** post-install 钩子，所以
「装完自动准备好浏览器」不能靠安装脚本，只能靠包内自带 + 启动器自愈。这一版的
`ensure_browser_exec()` 就是这个缺口上的补丁。

## 测试

新增：

- `tests/test_browser_payload.py`（10 项）：裁剪规则、清单、校验和、缺文件即失败。
- `tests/test_selfcontained_browser.py`（9 项）：浏览器默认路径、覆盖变量、自检中文提示、
  可执行位自愈、启动顺序。
- `tests/test_cjk_font_setup.py`（4 项）：用 conf.d 而不是覆盖 fonts.conf、字体路径指向包内、
  失败不影响启动。
- `tests/test_full_bundle.py`（8 项）：全量/精简两种包形状、无软链接、无路径穿越、
  chrome 保留可执行位、缺 chrome 立即失败、源码包不含二进制。
- `tests/test_agent_installer.py`（11 项）：真跑一遍 `install-agent.sh`（安装、保留登录资料、
  卸载、缺浏览器时报错退出）。
- `tests/test_release_zip_verifier.py`（5 项）+ `tests/verify_release_zip.py`：发布前的解包级校验。

全量套件 279 项通过、0 失败（25 项跳过：需要真机的 `test_discovery` 因掌机离线，
以及只有装了 playwright 才会跑的浏览器测试）。

## 已验证 / 未验证

- **已验证**：构建、打包、解包校验全链路在本机跑通；`install-agent.sh` 的真机逻辑用
  临时目录整体跑过（包括登录资料保留和卸载）。
- **未验证**：真机重新安装（掌机当前不在线）。浏览器二进制本身的渲染行为与 v1.2
  一致——同一个 Chromium 154、同一套启动参数，只是从「借来的」变成「自带的」。

## 升级说明

- 升级会替换 `weread/` 整目录和 `Weread.sh`，**登录资料
  `/storage/.config/weread-profile` 不受影响**。
- 旧的共享 Browser port 不会被删除，也不需要删除；新版本默认不再使用它。
- 如果之前手工配过 `/storage/.config/fontconfig/fonts.conf`，不影响——新配置写在
  `conf.d/` 里，两者并存。
