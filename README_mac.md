# VirtualCockroach（桌面宠物）macOS 打包与使用说明

一个透明全屏的桌面宠物：默认是几只大小不同的小狗在桌面上爬，会躲鼠标、钻出屏幕再从另一侧爬回、偶尔发呆；点击小狗会把它变成一只蟑螂，点击蟑螂则退出程序。

## 一、在 macOS 上打包

把仓库（至少包含 `cockroach.py`、`roach.png`、`icon.png`、`requirements.txt`、`build_mac.sh`）放到 Mac 上，打开终端进入该目录，执行：

```bash
bash build_mac.sh
```

脚本会依次完成：

1. 检查 `python3` 是否存在；缺失会提示 `brew install python3`。
2. 创建虚拟环境 `venv` 并安装依赖（`pillow`、`pyinstaller`、`pynput`）。
3. 用系统自带的 `sips` + `iconutil` 从 `icon.png` 生成 `icon.icns`（自动建 `.iconset`、多尺寸导出、再转 `.icns`）。
4. 用 PyInstaller 打包成单文件 App，并把 `roach.png` 一并打进包内。
5. 产物位于 `dist/VirtualCockroach.app`。

> 如果 `icon.png` 或 `roach.png` 缺失，脚本会友好报错并退出，不会继续执行。

## 二、首次运行需要授权

本程序用 [pynput](https://pypi.org/project/pynput/) 监听**全局鼠标位置**和**全局退出热键**。macOS 出于安全限制，这类全局监听需要在「系统设置 → 隐私与安全性 → 辅助功能（Accessibility）」中，把 `VirtualCockroach.app`（或运行它的终端）加入允许列表并勾选。

- 未授权时：全局热键（Cmd+Shift+Q）可能不生效，但**点击宠物退出仍然可用**，程序也能正常显示与移动。
- 授权后：全局热键即可正常工作。

## 三、如何退出

- **点击任意宠物**：
  - 点击**小狗** → 该只小狗立即变成蟑螂；
  - 点击**蟑螂** → 整个程序退出。
- **全局热键**：`Cmd + Shift + Q` 直接退出程序（需已授予辅助功能权限）。

## 四、已知 macOS 限制

- **透明窗口可能不跨所有桌面空间（Spaces）**：macOS 对无边框/透明窗口的跨 Space 行为有系统级限制，宠物可能只显示在当前桌面空间，而不会跟随切换到其他全屏/空间。这是平台限制，并非程序 bug。
- **辅助功能权限**：如前所述，未授权时全局热键不可用（点击退出不受影响）。
- **首次启动可能弹出“无法验证开发者”**：在「系统设置 → 隐私与安全性」中手动允许一次即可。

## 五、其他说明

- `get_global_mouse()` 在 Mac 上使用 pynput 读取光标位置，原点同样是屏幕左上角，与 tkinter 坐标一致，无需翻转。
- 小狗是**纯代码绘制**（PIL 在透明画布上画圆头、耳朵、身体、四腿、尾巴），不依赖任何图片素材；蟑螂沿用 `roach.png`。
