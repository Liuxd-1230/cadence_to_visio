# Cadence to Visio V2.0

Cadence to Visio V2.0 用于把 Cadence/Virtuoso 原理图导出的器件、走线和网表信息重建到 Microsoft Visio 中。

V2.0 的目标不是重新自动布线，而是尽量导出与 Virtuoso 中走线位置、器件位置一致的原理图。生成 Visio 后，可以在 Visio 中继续做少量手动微调和排版。

![example](example.svg)

## 文件说明

```text
cadence_to_visio_v2.py    V2.0 主入口，日常运行这个脚本即可
cadence_to_visio_core.py  核心解析、坐标转换、器件绘制和连接逻辑
circuit.vss               Visio stencil，包含 NMOS/PMOS/NPN/PNP/R/C/PIN 等 master
inst_info.txt             Virtuoso instance 坐标、方向和 BBox 信息
netlist.txt               CDL 网表，用于识别器件端口和 net
wires.xlsx                Virtuoso wire line 坐标表
example.svg               V2.0 导出效果示例图
export_inst_xy_orient.il  Virtuoso SKILL：导出 inst_info.txt
export_wire_lines_v4.il   Virtuoso SKILL：导出 wire line 坐标
```

## 环境依赖

在 Windows + Visio 环境下运行：

```powershell
pip install pywin32 openpyxl
```

`pywin32` 用于控制 Visio，`openpyxl` 用于读取 `wires.xlsx`。

## Virtuoso 数据导出

在 Virtuoso CIW 中加载并运行器件信息导出：

```lisp
load("/path/to/cadence_to_visio/export_inst_xy_orient.il")
c2vExportInstXYOrient("/path/to/cadence_to_visio/inst_info.txt")
```

在 Virtuoso CIW 中加载并运行 wire 坐标导出：

```lisp
load("/path/to/cadence_to_visio/export_wire_lines_v4.il")
c2vExportWireLinesV4("/path/to/cadence_to_visio/wires.tsv")
```

导出的 `wires.tsv` 可用 Excel 打开并另存为 `wires.xlsx`，覆盖本目录中的示例 `wires.xlsx`。

CDL 网表导出为 `netlist.txt`，放在本目录下。

## 运行方式

默认已经开启：

- 绘制 T 形交汇点 node；
- 将 wire endpoint 和 node 附着到器件 pin 或共享连接点；
- 使用普通 1D 线段保留 Virtuoso 原始走线形状，默认不使用 Visio 自动重路由 connector。

准备好 `inst_info.txt`、`netlist.txt`、`wires.xlsx` 后，直接运行：

```powershell
python .\cadence_to_visio_v2.py
```

只检查输入、不打开 Visio：

```powershell
python .\cadence_to_visio_v2.py --dry-run
```

## 常用选项

关闭附着：

```powershell
python .\cadence_to_visio_v2.py --no-attach
```

不绘制 node：

```powershell
python .\cadence_to_visio_v2.py --no-draw-nodes
```

显示 MOS B 端分支线：

```powershell
python .\cadence_to_visio_v2.py --draw-mos-b-wires
```

跳过指定 net：

```powershell
python .\cadence_to_visio_v2.py --skip-nets vdd,vss
```

使用其它 wire 坐标文件：

```powershell
python .\cadence_to_visio_v2.py --wires .\your_wires.xlsx
```

## V2.0 更新说明

- 以仓库根目录作为 V2.0 版本，不再把 `candence_to_visioV2.0` 作为子文件夹上传。
- 默认绘制 node，默认启用附着，运行 `cadence_to_visio_v2.py` 即可。
- wire 坐标以 Virtuoso 导出的线段为准，尽量保持与 Virtuoso 一样的走线。
- 器件位置以 Virtuoso instance 坐标和方向为准，尽量保持与 Virtuoso 一样的摆放。
- 支持 NMOS、PMOS、NPN、PNP、R、C、PIN 等常用器件识别和绘制。
- NPN/PNP connection points 按 `B, E, C` 对应 Base、Emitter、Collector。
- MOS 与 BJT 的 Visio anchor 偏移会按方向补偿，使符号位置和 Virtuoso 坐标对齐。
- 输出结果作为可编辑 Visio 原理图，后续在 Visio 中手动微调即可。

## 设计原则

- 走线坐标来自 Virtuoso 导出，不让 Visio 重新自动布线。
- 器件名使用独立文本框，不写入 master 本体。
- 附着只建立连接关系，不移动原始 wire endpoint 坐标。
- 先保证原理图拓扑、走线位置和器件位置一致，再在 Visio 中做人工美化。
