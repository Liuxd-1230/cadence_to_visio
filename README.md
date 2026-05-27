# Cadence to Visio V2.0

将 Cadence/Virtuoso 原理图导出的器件、网表和走线坐标重建到 Microsoft Visio。

目标：尽量保持与 Virtuoso 一样的器件位置和走线位置，生成可编辑的 Visio 原理图，后续在 Visio 中手动微调即可。

![example](example.svg)

## 主要文件

```text
cadence_to_visio_v2.py    主入口，直接运行
cadence_to_visio_core.py  解析、坐标转换和绘图逻辑
circuit.vss               Visio stencil
inst_info.txt             器件坐标、方向、BBox
netlist.txt               CDL 网表
wires.xlsx                Virtuoso wire 坐标
example.svg               示例图
old_cadence_to_visio/     旧版本和实验文件归档
```

## 安装

```powershell
pip install pywin32 openpyxl
```

需要 Windows + Microsoft Visio。

## 从 Virtuoso 导出

导出器件信息：

```lisp
load("/path/to/cadence_to_visio/export_inst_xy_orient.il")
c2vExportInstXYOrient("/path/to/cadence_to_visio/inst_info.txt")
```

导出走线坐标：

```lisp
load("/path/to/cadence_to_visio/export_wire_lines_v4.il")
c2vExportWireLinesV4("/path/to/cadence_to_visio/wires.tsv")
```

将 `wires.tsv` 用 Excel 另存为 `wires.xlsx`。CDL 网表保存为 `netlist.txt`。

## 运行

准备好 `inst_info.txt`、`netlist.txt`、`wires.xlsx` 后：

```powershell
python .\cadence_to_visio_v2.py
```

只检查输入：

```powershell
python .\cadence_to_visio_v2.py --dry-run
```

默认行为：

- 绘制 node；
- 启用附着；
- 保留 Virtuoso 走线形状；
- 不使用 Visio 自动重路由 connector。

## 常用选项

```powershell
python .\cadence_to_visio_v2.py --no-attach
python .\cadence_to_visio_v2.py --no-draw-nodes
python .\cadence_to_visio_v2.py --draw-mos-b-wires
python .\cadence_to_visio_v2.py --skip-nets vdd,vss
python .\cadence_to_visio_v2.py --wires .\your_wires.xlsx
```

## 支持器件

支持 NMOS、PMOS、NPN、PNP、R、C、PIN。

NPN/PNP 的 connection points 顺序为 `B, E, C`。MOS 和 BJT 的 Visio anchor 会按方向补偿，使符号位置与 Virtuoso 坐标对齐。
