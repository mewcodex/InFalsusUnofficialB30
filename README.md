# In Falsus Player Bests v1.06

Python 桌面生成器分支：[codex/python](https://github.com/mewcodex/InFalsusUnofficialB30/tree/codex/python)。C# 类库位于独立分支 [codex/csharp](https://github.com/mewcodex/InFalsusUnofficialB30/tree/codex/csharp)。

选择游戏 `.sav` 存档，填写名字、选择头像，点击「导出 PNG」。默认读取本机最新存档和对应 Steam 显示名；头像可自动读取存档当前角色。

输出 2700×3450 PNG。存档只读，运行无需游戏资源或网络。不支持成绩 CSV；支持自定义定数 CSV。

## 源码运行

需要 Python 3.10+ 和 Pillow：

```powershell
python -m pip install -r requirements.txt
python b30.py
python -m unittest -q test_b30.py
```

## 资源

内置 70 张曲绘、1 张背景和 5 张头像，来源见 assets/manifest.json。游戏美术和字体的权利归各自权利人所有。Cinzel 使用 SIL Open Font License，许可证位于 assets/fonts。曲名及数字使用游戏资源中的 Supreme，部分字符使用 Chiron Hei HK 或系统字体。

非官方评价：定数采用游戏等级.0，按 Arcaea 风格单谱成绩值计算最高 30 张平均值，不足 30 张补零。此值不代表游戏内评级。

界面支持 Windows 高 DPI 显示，窗口宽高比为 3:1。

曲名使用游戏简体中文语言设置对应的本地化文本；该字段为空时沿用原曲名。

## 构建 Windows 单文件 EXE

在解压后的源码目录执行：

```powershell
python -m pip install -r requirements-build.txt
python -m PyInstaller --noconfirm InFalsusB30.spec
```

输出为 `dist/InFalsusB30.exe`。配置使用相对项目路径，资源已内置，不需要安装游戏或运行拆包工具。发布版本 1.06，Windows 文件版本 1.0.6.0。

## 自定义定数

点击“生成定数表模板”保存 CSV，仅修改“定数”列。模板含全部 280 张谱面，默认为等级.0；定数须为非负数、最多一位小数。整数输入按 .0 使用。保留谱面ID和难度，允许重排行。导入成功后，在本次运行中用于定数显示、单谱成绩值、排序和总值；导入失败保留此前有效的表。重启恢复默认，或导入未修改的模板恢复默认。命令行可用 --constants 指定 CSV 文件。
