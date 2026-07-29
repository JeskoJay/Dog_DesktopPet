# 小狗桌宠 · VirtualCockroach

一个透明、无边框、全屏运行的桌面宠物（Python + tkinter + PIL）。
默认是一只程序绘制的小柯基在桌面上溜达，会**躲鼠标、追鼠标、钻出屏幕再从另一侧爬回、偶尔发呆**；
点击小狗会让它“炸”成一只经典蟑螂，点击蟑螂则退出程序。

> 仓库原名 `VirtualCockroach`：最初是“点狗变蟑螂”的彩蛋，后来把主角狗重绘成了彩色卡通柯基，并调得更活泼。
> “宇哥帮帮遛”那套爆蟑螂菜单是另一个项目（`Maltese_DesktopPet`）的移植，本仓库仅保留桌面宠物本体与测试。

---

## ✨ 特性

- 🐕 **纯代码绘制的柯基**：圆头、两只大立耳、双大眼 + 高光、大鼻头、粉舌头、黄项圈、短粗腿、小翘尾。
  - 头部单独绘制后逆时针预旋转 90°，经全局旋转后正面朝上、双耳向上、双眼左右并排。
  - 6 个姿态：`walk / sit / sleep / chase / stretch / look`（sleep 闭眼闭嘴、无舌）。
- 🪳 **经典蟑螂**：沿用 `roach.png`，带动画触角；从点击点径向爆开、随机游走、遇鼠标近则警觉/恐慌逃离、边界转向回避。
- 🖱️ **活泼的行为**：
  - 散步 / 追鼠标速度可调，姿态切换频繁。
  - 鼠标移动时小狗会屁颠屁颠追光标。
- 🪟 **跨平台**：用 `pynput` 读取全局鼠标位置与注册全局退出热键，**不依赖 Windows 专属 API**。
- 🧪 **自带测试**：`test_pet.py` / `test_roach.py` / `qa_dog_check.py` 验证几何与行为。

---

## 🧰 技术栈

| 用途 | 库 |
|------|----|
| 界面 / 透明窗口 | `tkinter`（标准库） |
| 图像绘制 | `Pillow (PIL)` |
| 打包为 exe | `PyInstaller` |
| 全局鼠标 / 热键 | `pynput` |

依赖见 [`requirements.txt`](requirements.txt)：

```
pillow>=10
pyinstaller>=6
pynput>=1.7
```

---

## 📁 目录结构

```
.
├── cockroach.py            # 主程序：宠物本体、状态机、爆蟑螂逻辑
├── roach.png               # 蟑螂精灵图（带透明通道）
├── cockroach.png           # 柯基预览/参考素材
├── cockroach_clean.png
├── cockroach_preview.png
├── dog_preview.png         # 6 姿态预览图
├── icon.ico / icon.png     # 程序图标
├── ref_main_x3.png / ref_col_x4.png   # 造型参考图
├── VirtualCockroach.spec   # PyInstaller 打包配置（Windows）
├── build_mac.sh            # macOS 一键打包脚本
├── requirements.txt        # Python 依赖
├── test_pet.py             # 几何/朝向测试
├── test_roach.py           # 蟑螂几何测试
├── qa_dog_check.py         # 行为随机性 QA（确定性 seed）
├── qa_behavior_check.py    # 行为检查
├── verify_face.py          # 把狗头/脸渲染成 ASCII 以便核对造型
├── verify_rotation.py      # 旋转方向校验
├── render_final_preview.py # 生成 dog_preview.png
├── render_dog_*.py         # 其他预览/调试脚本
├── README.md               # 本文件
└── README_mac.md           # macOS 打包与使用说明（中文）
```

> 说明：`.workbuddy/`、`build/`、`dist/`、`__pycache__/` 已被 `.gitignore` 忽略，不纳入版本控制。

---

## 🚀 快速开始（从源码运行）

需要 Python 3.10+。

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 运行
python cockroach.py
```

程序启动后会在桌面出现一只小狗；点击小狗变蟑螂，点击蟑螂退出。

---

## 📦 打包成可执行文件

### Windows

```bash
pip install pyinstaller
pyinstaller VirtualCockroach.spec --noconfirm
```

产物在 `dist/VirtualCockroach.exe`（本仓库不提交 `dist/`，请本地构建）。

> 注意：PyInstaller 需要在干净环境下运行。若遇到「安全删除」拦截导致收尾删除旧文件失败，
> 可在打包前清空 `PYTHONPATH`（例如 `PYTHONPATH= pyinstaller ...`）以使用原生删除。

### macOS

将仓库放到 Mac 上，终端进入目录执行：

```bash
bash build_mac.sh
```

脚本会创建虚拟环境、安装依赖、用系统 `sips`/`iconutil` 从 `icon.png` 生成 `icon.icns`，
再用 PyInstaller 打包成 `dist/VirtualCockroach.app`。

首次运行需在「系统设置 → 隐私与安全性 → 辅助功能」中授权（全局热键需要）；
未授权时点击退出仍可用。详见 [`README_mac.md`](README_mac.md)。

---

## 🎮 操作说明

| 操作 | 效果 |
|------|------|
| 点击小狗 | 该只小狗消失，炸出 5 只蟑螂 |
| 点击蟑螂 | 整个程序退出 |
| 移动鼠标 | 小狗会追着光标跑（活泼模式） |
| `Ctrl + Shift + Q`（Win/Linux）<br>`Cmd + Shift + Q`（macOS） | 退出程序 |

---

## 🐾 设计小贴士

- **朝向约定**：精灵图“头朝上”绘制，全局旋转 `-90°` 后头朝 `+x`（前进方向）。
  几何保证 `head_offset_in_base` 对狗和蟑螂都返回 `hoff_x > 0`，因此头永远朝向运动方向。
- **活泼调参**（在 `cockroach.py` 顶部常量）：
  - `DOG_CHASE_SPEED` / `DOG_WALK_SPEED`：追鼠 / 散步速度
  - `DOG_POSE_TIME` / `DOG_SLEEP_TIME`：姿态 / 睡眠停留时长（越短切换越频）
  - `TURN_RATE`：转向跟手程度
  - 追鼠触发概率（`moved > 阈值 and random() < p`）：光标一动就追的灵敏度

---

## 📝 许可 / 说明

- 蟑螂精灵 `roach.png` 与造型参考图来自原始 `VirtualCockroach` 项目。
- 柯基造型为程序绘制，可按需调整常量。
- 本仓库为个人桌面宠物玩具，欢迎自行改着玩。
