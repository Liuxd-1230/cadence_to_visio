# Cadence to Visio V2.0

这是一个从 Cadence/Virtuoso 原理图导出数据并在 Visio 中重建图形的整理版目录。

## 目录内容

```text
circuit.vss               Visio stencil，包含 NMOS/PMOS/R/C/PIN 等 master
inst_info.txt             Virtuoso instance 坐标、方向、BBox 信息
netlist.txt               CDL 网表，用于识别器件端口和 net
export_inst_xy_orient.il  Virtuoso SKILL：导出 inst_info.txt
export_wire_lines_v4.il   Virtuoso SKILL：导出 wire line 坐标表
cadence_to_visio_core.py  核心函数库，负责解析、坐标、过滤和基础绘图逻辑
cadence_to_visio_v2.py    V2.0 主入口脚本
README.md                 中文说明文档
```

注意：绘制 wire 仍需要 `wires.xlsx`。如果同目录没有该文件，请通过 `--wires` 指定路径。

## 环境依赖

在 Windows + Visio 环境下运行：

```powershell
pip install pywin32 openpyxl
```

`pywin32` 用于控制 Visio，`openpyxl` 用于读取 `wires.xlsx`。

## Virtuoso 数据导出

在 CIW 中加载并运行器件信息导出：

```lisp
load("/path/to/candence_to_visioV2.0/export_inst_xy_orient.il")
c2vExportInstXYOrient("/path/to/candence_to_visioV2.0/inst_info.txt")
```

在 CIW 中加载并运行 wire 坐标导出：

```lisp
load("/path/to/candence_to_visioV2.0/export_wire_lines_v4.il")
c2vExportWireLinesV4("/path/to/candence_to_visioV2.0/wires.tsv")
```

`cadence_to_visio_v2.py` 默认读取 `wires.xlsx`。导出 `wires.tsv` 后，可用 Excel 打开并另存为 `wires.xlsx`，或在运行时通过 `--wires` 指定已经整理好的 xlsx 文件。

## 推荐运行方式

默认推荐使用稳定模式：普通 1D 线段 + 端点附着。

```powershell
python .\cadence_to_visio_v2.py --wires ..\wires.xlsx --no-draw-nodes
```

如果 `wires.xlsx` 已放在当前 V2.0 目录内：

```powershell
python .\cadence_to_visio_v2.py --no-draw-nodes
```

## 两个全局控制开关

### 是否附着端点

默认启用附着：

```powershell
--attach
```

关闭附着：

```powershell
--no-attach
```

启用附着时：

- wire endpoint 如果与器件 pin 坐标重合，会 Glue 到器件 `Connections.Xn/Yn`。
- wire endpoint 如果不是器件 pin，会 Glue 到同一 net、同一坐标的共享隐藏连接点。
- T 形交汇点 node 如果绘制，也会 Glue 到对应共享连接点。
- 不会移动原始 wire endpoint 坐标。

### 是否使用 Visio 内置连接线

默认不使用 Visio 内置连接线：

```powershell
--no-visio-connectors
```

启用 Visio 内置 Dynamic Connector：

```powershell
--visio-connectors
```

建议默认关闭。Visio 内置连接线可能触发自动路由，导致线段形状变化；只有在需要 Visio 原生 connector 行为时再开启。

## 常用选项

隐藏 MOS B 端分支线，默认就是隐藏：

```powershell
--no-draw-mos-b-wires
```

显示 MOS B 端分支线：

```powershell
--draw-mos-b-wires
```

不绘制 T 形交汇点 node：

```powershell
--no-draw-nodes
```

只检查输入，不打开 Visio：

```powershell
--dry-run
```

跳过指定 net：

```powershell
--skip-nets vdd,vss
```

翻转 Y 轴：

```powershell
--flip-y
```

## 推荐测试流程

1. 先 dry-run 检查输入：

```powershell
python .\cadence_to_visio_v2.py --wires ..\wires.xlsx --dry-run
```

2. 再用稳定模式绘图：

```powershell
python .\cadence_to_visio_v2.py --wires ..\wires.xlsx --no-draw-nodes
```

3. 如果想完全不建立 Visio Glue 关系：

```powershell
python .\cadence_to_visio_v2.py --wires ..\wires.xlsx --no-attach --no-draw-nodes
```

4. 如果想实验 Visio 内置连接线：

```powershell
python .\cadence_to_visio_v2.py --wires ..\wires.xlsx --visio-connectors --no-draw-nodes
```

## 设计原则

- wire 坐标以 Virtuoso 导出为准。
- 默认不让 Visio 自动改线。
- 器件名称使用独立文本框，不写入器件 master 本体。
- MOS B 分支过滤默认开启，并保留 S 到 VDD/VSS 交汇点方向的必要竖线。
- 端点附着只在不改变原始坐标的前提下进行。
