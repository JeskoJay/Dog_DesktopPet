# 马尔济斯桌面宠物「宇哥帮帮遛 → 爆蟑螂」移植

## 完成内容

把 `VirtualCockroach` 的「爆蟑螂」效果移植到另一个独立项目 `D:\Maltese_DesktopPet`（PyQt5 马尔济斯桌面宠物），并在右键菜单新增条目《宇哥帮帮遛》。

- **新增菜单项**：右键宠物 → 「宇哥帮帮遛」
- **触发效果**：马尔济斯暂时隐身，从宠物当前位置**径向爆开 5 只蟑螂**（与 `VirtualCockroach` 原始逻辑一致），随后每只蟑螂自由游走 / 停顿，鼠标靠近时会**逃离**（200px 内警觉逃、90px 内恐慌冲向屏幕边缘），靠近屏幕边缘会**转向回避**（不再反弹），身体随朝向旋转并带**动画触角**；9 秒后蟑螂群消失，马尔济斯恢复常态。
- **资源**：从当前项目复制 `roach.png` 到 `D:\Maltese_DesktopPet\Image\roach.png`（被 spec 的 `datas=[('Image','Image')]` 自动打包）。
- **代码改动**：仅修改 `D:\Maltese_DesktopPet\main.py`
  - 导入 `math`、`QTransform`、`QPainter`、`QPen`、`QPolygonF`、`QColor`、`QPointF`
  - `RoachSwarm` 类**整段重写**，1:1 移植 `cockroach.py` 的经典蟑螂行为（5 只径向爆裂、游走/暂停/逃离状态机、朝向平滑、边界转向回避、动画触角）
  - `DesktopPet` 新增 `burstRoaches()` / `_endRoaches()` / `_cleanup_roaches()`；`burstRoaches` 把宠物屏幕中心作为爆裂原点传给 `RoachSwarm(origin=...)`
  - `showMenu()` 中加入 `menu.addAction(u"宇哥帮帮遛", self.burstRoaches)`

## 打包

构建环境为项目自带的 venv（`D:\Maltese_DesktopPet\venv`）。首次打包因 spec 使用 `icon=['Image\\MenuIcon.jpg']`、而 venv 缺少 Pillow 导致图标转换失败；已安装 Pillow 后重新打包成功。

输出 exe：
```
D:\Maltese_DesktopPet\dist\Maltese_DesktopPet.exe
```

冒烟测试：`timeout 5 D:/Maltese_DesktopPet/dist/Maltese_DesktopPet.exe` → EXIT=124（程序正常存活）。

## 使用方式

1. 双击 `D:\Maltese_DesktopPet\dist\Maltese_DesktopPet.exe` 启动宠物。
2. 在宠物上右键 → 选择「宇哥帮帮遛」。
3. 马尔济斯隐身，蟑螂群出现并乱窜 9 秒，之后宠物恢复。
4. 原有「遛小鸡毛」等功能保持不变。
