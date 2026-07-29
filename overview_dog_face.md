# 线条小狗 · 重画狗脸（侧脸犬科）

## 做了什么
用户："这脸不像狗，你自己画个狗脸。" 推翻上一版卡通线条脸（圆头+两只耷拉耳+两只圆点眼+小鼻+w嘴），把头部/脸重画成一眼读得出是狗的**侧脸**。

## 新头部设计（cockroach.py · draw_dog_state）
保持身体、腿、尾、6 姿态、头朝上 / -90 旋转约定、hoff 几何全不动，只换头部与脸部：
- **脑壳**：圆/卵形椭球（HEAD_RX=50, HEAD_RY=44）
- **口鼻/muzzle**：从脑壳向上（画布）伸出、尖端在圆头最上的叶片形 → 转 -90 后朝前（游戏右）
- **鼻头**：深色椭圆画在口鼻尖端（游戏内最前）
- **眼睛**：侧脸画**一只**明显的深色圆点，落在脑壳上（退后在口鼻之后）
- **耷拉耳**：从脑壳后上方起笔、往下垂（画布右下=游戏下）的叶片形，像拉布拉多/金毛
- **嘴**：口鼻下方一条深色嘴线

细节（眼/鼻/嘴）仍在 `_ld_finish` 之后用深色描边画到 RGBA 图上，沿用单一掩膜 + 粗描边风格。

## 验证
- **ASCII 目检**（verify_face.py，3× 缩放，模型读不了 PNG）：头部清晰读得出是狗——脑壳 + 向上伸出的口鼻 + 尖端鼻头 + 脑壳上的眼 + 下垂耷拉耳 + 嘴线。
- **测试全绿**：`test_pet.py` → ALL_PET_TESTS_PASSED；`test_roach.py` → ALL_GEOMETRY_TESTS_PASSED；`qa_dog_check.py` → QA_DOG_OK（chase/look/sleep/stretch/walk 共 5 姿态）。
- **构建**：`Build complete!`；`dist/VirtualCockroach.exe` 刷新到 11:16；冒烟 `timeout 5` 退出码 124（存活未崩），`err_exe.txt`/`err_py.txt` 为空。

## 踩坑记录
- 工程师子智能体回报 "completed" 但**文件压根没改**（mtime 仍 10:23，头部代码逐字未动）——空跑/假成功。主理人独立验证（读文件 + stat mtime）识破，按用户"你自己画"的指令**亲自重画**，未把"completed"当真。

## 交付物
- `dist/VirtualCockroach.exe` — 含新狗脸的侧剖面线条小狗桌面宠物
- `dog_preview.png` — 6 姿态预览图（新脸）
- `cockroach.py` — 源码头/脸重画（draw_dog_state）
