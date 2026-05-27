# Exact Virtuoso-to-Visio Drawing Strategy

This strategy stops using the CDL netlist as a router. The CDL netlist is only a
connectivity check. Geometry comes from the Virtuoso schematic database export.

## Inputs

- `wires.xlsx`: authoritative wire geometry exported from Virtuoso.
  Required columns: `group_id`, `seg_id`, `net`, `obj_type`, `layer`, `purpose`,
  `x1`, `y1`, `x2`, `y2`.
- `inst_info.txt`: authoritative instance placement exported from Virtuoso.
  Required fields: instance name, cell name, XY, orient, BBox.
- `netlist.txt`: CDL connectivity, used for validation only.
- `circuit.vss`: Visio stencil used to draw device symbols.

## Drawing Rules

1. Draw every instance from `inst_info.txt`.
   - Treat `XY` as the Virtuoso symbol anchor, not always the center.
   - Anchor-to-center correction uses a base offset in R0 orientation, then
     applies the instance `Orient` transform to that vector.
   - MOS base offset: `(VisioWidth / 2, 0)`.
   - R/C base offset: `(0, -VisioHeight / 2)`.
   - Supported transforms: `R0=(x,y)`, `R90=(-y,x)`, `R180=(-x,-y)`,
     `R270=(y,-x)`, `MX=(x,-y)`, `MY=(-x,y)`, `MXR90=(y,x)`,
     `MYR90=(-y,-x)`.
   - Instance names are not written into the device symbol text. A separate
     transparent text box is drawn beside each final visible device.
   - Use the Virtuoso BBox only for symbol width and height.
   - Optional placement corrections can be added in `placement_offsets.tsv`
     using `global`, `type`, `cell`, or `inst` rules. Offsets are applied in
     Virtuoso coordinate units before the global Visio page translation.
   - Use the Virtuoso orient value for rotation and mirror.
   - By default, keep the native size of each `circuit.vss` master
     (`--symbol-fit native`) to avoid distorting symbols.
   - If no matching stencil master is found, draw a fallback rectangle with the
     instance name and cell name, rather than skipping the object.

2. Use original wire endpoint coordinates by default.
   - Default `--wire-adjust none` preserves the coordinates from `wires.xlsx`.
   - Use `--wire-adjust snap-endpoints` only when device-facing dangling
     endpoints should be micro-adjusted to symbol pins.
   - When MOS B-pin branches are hidden, segments from the starting B pin up to
     the first real T-shaped wire junction are not drawn.
   - The starting B pin is matched from two candidate locations: the generic
     BBox-based B-pin hint and the MOS body endpoint offset from the symbol
     anchor. For the current Visio MOS symbol, the body endpoint offset is
     `6.35 mm` in the R0 +X direction, transformed by the instance `Orient`.
     Branches from both matched B vertices are removed up to their first real T.
   - If that removal also catches vertical segments on `VDD`/`VSS` that lie
     between the true MOS `S` pin and a same-x real T-shaped power junction,
     those segments are restored and drawn. For `VDD` the target junction is
     searched upward; for `VSS` it is searched downward. The segment does not
     have to start exactly at the `S` pin.
   - Optional: remove whole nets with `--skip-nets`, for example
     `--skip-nets vdd,vss`. Skipped nets are removed before endpoint snapping and
     before drawing.
   - Optional: use `--skip-mos-body-nets` to remove every net connected to an
     NMOS/PMOS `B` pin in the CDL netlist.
   - Optional: use `--exclude-pins B` if body pins should not participate in
     endpoint snapping. By default, no pins are excluded.
   - Find dangling wire endpoints in `wires.xlsx` by net-local degree:
     endpoints that occur only once in that net's wire graph are treated as
     device-facing endpoints.
   - For each dangling endpoint, use its net name to find same-net device pins
     from `netlist.txt`.
   - After placing native `circuit.vss` symbols, read each candidate pin's actual
     Visio connection point.
   - Replace the dangling endpoint coordinate with the nearest same-net device
     connection point.
   - Write the adjusted coordinates to `wires_adjusted.xlsx`.
   - Write every coordinate change to `wire_adjustments.tsv`.

3. Draw every schematic wire from the adjusted wire coordinates.
   - Each row is a real Virtuoso wire segment.
   - Draw `x1,y1 -> x2,y2` directly.
   - Do not run MST, orthogonal routing, or Visio automatic connector routing.
   - Do not glue wire endpoints to Visio connection points, because glue can move
     endpoints and break exact geometry.
   - Native `circuit.vss` symbols can therefore keep their original size while
     device-facing wire endpoints are locally snapped to the actual symbol pins.

4. Keep one coordinate transform for all objects.
   - Default behavior translates the complete Virtuoso drawing into the positive
     Visio page area while preserving all relative distances exactly.
   - `--preserve-absolute` keeps raw Virtuoso coordinates.
   - `--flip-y` is available only if the target page coordinate system needs it.

5. Use the CDL netlist as both a pin lookup table and a report.
   - Missing instances are reported.
   - Nets present in the netlist but absent from wires are reported.
   - Nets present in wires but absent from the netlist are reported.

## Guarantee Boundary

With the current inputs, wire geometry can be reproduced exactly up to the chosen
global coordinate transform. Full visual identity also requires matching symbols,
labels, pin graphics, junction dots, comments, and display-resource colors. If
those must be exact too, export label/text objects and symbol geometry from
Virtuoso, or make `circuit.vss` masters match the Virtuoso symbols exactly.

## Junction Optimization Script

`cadence_to_visio_exact_with_junction_opt.py` is a separate script layered on top
of the endpoint-snapping flow. It does not replace
`cadence_to_visio_exact_from_wires.py`.

After endpoint snapping, it optimizes internal junctions before drawing:

- V junctions: degree-2 points whose two incident segments are not axis-aligned.
  The junction is moved left, right, up, or down only, choosing a one-axis move
  that makes the two incident segments orthogonal.
- Y junctions: degree-3 points that are not T-shaped. The junction is moved
  left, right, up, or down only, choosing a one-axis move that makes the three
  incident segments form an orthogonal T.
- The optimizer writes `wires_adjusted_optimized.xlsx`.
- The optimizer writes `junction_optimizations.tsv` with every moved junction.
