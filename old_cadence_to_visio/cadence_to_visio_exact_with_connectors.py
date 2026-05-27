"""Draw exact Virtuoso wires as Visio built-in dynamic connectors.

This variant intentionally reuses the parser, placement, filtering, and device
drawing logic from cadence_to_visio_exact_from_wires.py. Only the visible wire
segments are replaced by Visio connector shapes whose endpoints are glued to
hidden endpoint anchors.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import cadence_to_visio_exact_from_wires as base


Point = Tuple[float, float]
EndpointKey = Tuple[str, Point]

ANCHOR_SIZE = 0.01
ADAPTER_ANCHOR_NET = "__ADAPTER__"


@dataclass
class GlueTarget:
    shape: object
    conn_idx: Optional[int] = None


def set_formula(shape, cell_name: str, formula: str) -> None:
    try:
        shape.CellsU(cell_name).FormulaU = formula
    except Exception:
        pass


def set_result(shape, cell_name: str, value: float) -> None:
    try:
        shape.CellsU(cell_name).ResultIU = value
    except Exception:
        pass


def make_endpoint_anchor(page, point: Point):
    x, y = point
    half = ANCHOR_SIZE / 2
    anchor = page.DrawRectangle(x - half, y - half, x + half, y + half)
    anchor.Text = ""
    set_formula(anchor, "LinePattern", "0")
    set_formula(anchor, "FillPattern", "0")
    set_formula(anchor, "LockWidth", "1")
    set_formula(anchor, "LockHeight", "1")
    set_formula(anchor, "LockMoveX", "1")
    set_formula(anchor, "LockMoveY", "1")
    set_formula(anchor, "LockSelect", "1")
    return anchor


def ensure_anchor(
    page,
    anchors: Dict[EndpointKey, object],
    key: EndpointKey,
    point: Point,
):
    anchor = anchors.get(key)
    if anchor is None:
        anchor = make_endpoint_anchor(page, point)
        anchors[key] = anchor
    return anchor


def endpoint_key(segment: base.WireSegment, point: Point) -> EndpointKey:
    return (base.normalize_net(segment.net), base.point_key(point))


def create_endpoint_anchors(
    page,
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
) -> Dict[EndpointKey, object]:
    anchors: Dict[EndpointKey, object] = {}
    for segment in wires:
        for virt_point in (segment.p1, segment.p2):
            key = endpoint_key(segment, virt_point)
            ensure_anchor(page, anchors, key, coord.point(virt_point))
    return anchors


def format_connector(connector, weight: str = base.WIRE_WEIGHT) -> None:
    connector.Text = ""
    set_formula(connector, "LineWeight", weight)
    set_formula(connector, "LineColor", base.WIRE_COLOR)
    set_formula(connector, "LinePattern", "1")
    set_formula(connector, "BeginArrow", "0")
    set_formula(connector, "EndArrow", "0")
    set_formula(connector, "ShapeRouteStyle", "16")
    set_formula(connector, "ConLineRouteExt", "1")


def drop_dynamic_connector(visio, page, begin: Point, end: Point, weight: str = base.WIRE_WEIGHT):
    mid_x = (begin[0] + end[0]) / 2
    mid_y = (begin[1] + end[1]) / 2
    connector = page.Drop(visio.ConnectorToolDataObject, mid_x, mid_y)
    set_result(connector, "BeginX", begin[0])
    set_result(connector, "BeginY", begin[1])
    set_result(connector, "EndX", end[0])
    set_result(connector, "EndY", end[1])
    format_connector(connector, weight)
    return connector


def glue_endpoint_to_target(connector, endpoint: str, target: GlueTarget) -> bool:
    x_cell = connector.CellsU(f"{endpoint}X")
    y_cell = connector.CellsU(f"{endpoint}Y")

    if target.conn_idx is not None:
        try:
            x_cell.GlueTo(target.shape.CellsU(f"Connections.X{target.conn_idx}"))
            y_cell.GlueTo(target.shape.CellsU(f"Connections.Y{target.conn_idx}"))
            return True
        except Exception:
            pass

    try:
        x_cell.GlueToPos(target.shape, 0.5, 0.5)
        return True
    except Exception:
        pass

    try:
        x_cell.GlueTo(target.shape.CellsU("PinX"))
        y_cell.GlueTo(target.shape.CellsU("PinY"))
        return True
    except Exception:
        return False


def draw_connector_between(
    visio,
    page,
    begin: Point,
    end: Point,
    begin_target: GlueTarget,
    end_target: GlueTarget,
    weight: str = base.WIRE_WEIGHT,
) -> Tuple[object, int]:
    connector = drop_dynamic_connector(visio, page, begin, end, weight)
    glue_failures = 0
    if not glue_endpoint_to_target(connector, "Begin", begin_target):
        glue_failures += 1
    if not glue_endpoint_to_target(connector, "End", end_target):
        glue_failures += 1
    try:
        connector.SendToBack()
    except Exception:
        pass
    return connector, glue_failures


def draw_wire_connectors(
    visio,
    page,
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
) -> Tuple[Dict[EndpointKey, object], int, int]:
    anchors = create_endpoint_anchors(page, wires, coord)
    connector_count = 0
    glue_failures = 0

    for segment in wires:
        p1 = coord.point(segment.p1)
        p2 = coord.point(segment.p2)
        begin_anchor = anchors[endpoint_key(segment, segment.p1)]
        end_anchor = anchors[endpoint_key(segment, segment.p2)]
        _connector, failures = draw_connector_between(
            visio,
            page,
            p1,
            p2,
            GlueTarget(begin_anchor),
            GlueTarget(end_anchor),
        )
        connector_count += 1
        glue_failures += failures

    return anchors, connector_count, glue_failures


def draw_orthogonal_adapter_connectors(
    visio,
    page,
    anchors: Dict[EndpointKey, object],
    start: Point,
    end: Point,
    start_target: GlueTarget,
    end_target: GlueTarget,
) -> Tuple[int, int]:
    if math.sqrt(base.distance_sq(start, end)) <= base.PIN_ADAPTER_EPS:
        return 0, 0

    if abs(start[0] - end[0]) < base.PIN_ADAPTER_EPS or abs(start[1] - end[1]) < base.PIN_ADAPTER_EPS:
        _connector, failures = draw_connector_between(
            visio,
            page,
            start,
            end,
            start_target,
            end_target,
            base.PIN_ADAPTER_WEIGHT,
        )
        return 1, failures

    if abs(start[0] - end[0]) >= abs(start[1] - end[1]):
        elbow = (end[0], start[1])
    else:
        elbow = (start[0], end[1])

    elbow_key = (ADAPTER_ANCHOR_NET, base.point_key(elbow))
    elbow_anchor = ensure_anchor(page, anchors, elbow_key, elbow)
    elbow_target = GlueTarget(elbow_anchor)

    _connector1, failures1 = draw_connector_between(
        visio,
        page,
        start,
        elbow,
        start_target,
        elbow_target,
        base.PIN_ADAPTER_WEIGHT,
    )
    _connector2, failures2 = draw_connector_between(
        visio,
        page,
        elbow,
        end,
        elbow_target,
        end_target,
        base.PIN_ADAPTER_WEIGHT,
    )
    return 2, failures1 + failures2


def draw_pin_adapters_as_connectors(
    visio,
    page,
    devices: Sequence[base.NetDevice],
    instances: Dict[str, base.Instance],
    shapes: Dict[str, object],
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
    threshold: float,
    excluded_pins: Set[str],
    anchors: Dict[EndpointKey, object],
) -> Tuple[int, int]:
    vertices = base.wire_vertices_by_net(wires)
    adapter_count = 0
    glue_failures = 0

    for device in devices:
        inst = instances.get(device.name)
        shape = shapes.get(device.name)
        if inst is None or shape is None:
            continue

        pin_order = base.DEVICE_PIN_ORDER.get(inst.dev_type, [])
        for pin, net in device.pins.items():
            if pin.upper() in excluded_pins or pin not in pin_order:
                continue

            conn_idx = pin_order.index(pin) + 1
            start = base.connection_page_point(page, shape, conn_idx)
            if start is None:
                continue

            pin_virt_point = coord.inverse_point(start)
            wire_virt_point = base.nearest_wire_vertex(net, vertices, pin_virt_point, threshold)
            if wire_virt_point is None:
                continue

            end = coord.point(wire_virt_point)
            if math.sqrt(base.distance_sq(start, end)) <= base.PIN_ADAPTER_EPS:
                continue

            wire_key = (base.normalize_net(net), base.point_key(wire_virt_point))
            wire_anchor = ensure_anchor(page, anchors, wire_key, end)
            count, failures = draw_orthogonal_adapter_connectors(
                visio,
                page,
                anchors,
                start,
                end,
                GlueTarget(shape, conn_idx),
                GlueTarget(wire_anchor),
            )
            adapter_count += count
            glue_failures += failures

    return adapter_count, glue_failures


def bring_devices_to_front(shapes: Dict[str, object]) -> None:
    for shape in shapes.values():
        try:
            shape.BringToFront()
        except Exception:
            pass


def draw_device_labels(
    page,
    instances: Dict[str, base.Instance],
    shapes: Dict[str, object],
) -> int:
    count = 0
    for name, inst in instances.items():
        shape = shapes.get(name)
        if shape is None:
            continue
        base.draw_device_label(page, inst, shape)
        count += 1
    return count


def draw_visio_with_connectors(
    instances: Dict[str, base.Instance],
    devices: Sequence[base.NetDevice],
    wires: Sequence[base.WireSegment],
    stencil_path: str,
    coord: base.CoordMap,
    symbol_fit: str,
    wire_adjust: str,
    pin_snap_threshold: float,
    excluded_pins: Set[str],
    placement_offsets: Sequence[base.PlacementOffsetRule],
    adjusted_wires_path: str,
    adjustment_report_path: str,
    draw_nodes: bool = True,
    visible: bool = True,
) -> None:
    try:
        import win32com.client
    except ImportError as exc:
        raise RuntimeError("pywin32 is required for Visio drawing. Install with: pip install pywin32") from exc

    visio = win32com.client.Dispatch("Visio.Application")
    visio.Visible = visible
    visio.Documents.Add("")
    page = visio.ActivePage

    min_x, min_y, max_x, max_y = coord.bbox(coord.bounds)
    page_sheet = page.PageSheet
    page_sheet.CellsU("PageWidth").ResultIU = max(1.0, max_x - min_x + base.PAGE_MARGIN)
    page_sheet.CellsU("PageHeight").ResultIU = max(1.0, max_y - min_y + base.PAGE_MARGIN)

    stencil = None
    if stencil_path and os.path.exists(stencil_path):
        stencil = visio.Documents.OpenEx(os.path.abspath(stencil_path), 64)
    master_index = base.build_master_index(stencil)

    shapes: Dict[str, object] = {}
    for inst in instances.values():
        shapes[inst.name] = base.draw_instance(
            page,
            master_index,
            inst,
            coord,
            symbol_fit,
            placement_offsets,
            draw_label=False,
        )

    adjustments: List[base.WireAdjustment] = []
    dangling_count = 0
    if wire_adjust == "snap-endpoints":
        dangling_count = len(base.find_dangling_endpoint_refs(wires))
        adjustments = base.snap_dangling_wire_endpoints(
            page,
            wires,
            devices,
            instances,
            shapes,
            coord,
            pin_snap_threshold,
            excluded_pins,
            placement_offsets,
        )
        base.write_wires_xlsx(adjusted_wires_path, wires)
        base.write_adjustments_tsv(adjustment_report_path, adjustments)

    anchors, connector_count, glue_failures = draw_wire_connectors(visio, page, wires, coord)
    node_count = base.draw_t_junction_nodes(page, master_index, wires, coord) if draw_nodes else 0

    adapter_count = 0
    adapter_glue_failures = 0
    if wire_adjust == "adapters":
        adapter_count, adapter_glue_failures = draw_pin_adapters_as_connectors(
            visio,
            page,
            devices,
            instances,
            shapes,
            wires,
            coord,
            pin_snap_threshold,
            excluded_pins,
            anchors,
        )

    bring_devices_to_front(shapes)
    label_count = draw_device_labels(page, instances, shapes)

    total_glue_failures = glue_failures + adapter_glue_failures
    print(f"Drew {len(instances)} instances and {connector_count} Visio connector wire segment(s)")
    print(f"Created {len(anchors)} hidden endpoint anchor(s); glue failures: {total_glue_failures}")
    if draw_nodes:
        print(f"Added {node_count} T-junction node(s) and {label_count} device label(s)")
    else:
        print(f"Skipped T-junction nodes; added {label_count} device label(s)")
    if wire_adjust == "snap-endpoints":
        print(f"Found {dangling_count} dangling wire endpoints; snapped {len(adjustments)}")
        print(f"Wrote adjusted wires to {adjusted_wires_path}")
        print(f"Wrote adjustment report to {adjustment_report_path}")
    if wire_adjust == "adapters":
        print(f"Added {adapter_count} local pin adapter connector segment(s)")


def main() -> None:
    args = base.parse_args()
    instances = base.parse_instances(args.inst_info)
    devices = base.parse_netlist(args.netlist, instances)
    wires = base.read_wires_xlsx(args.wires)
    placement_offsets = base.parse_placement_offsets(args.placement_offsets)

    for message in base.validate_inputs(instances, devices, wires):
        print(message)

    skip_nets = base.parse_net_set(args.skip_nets)
    if args.skip_mos_body_nets:
        body_nets = base.mos_body_nets(devices)
        skip_nets.update(body_nets)
        print(f"MOS body nets from netlist: {', '.join(sorted(body_nets)) if body_nets else '(none)'}")

    wires, skipped_wire_count = base.filter_wires_by_net(wires, skip_nets)
    if skip_nets:
        print(f"Skipping nets: {', '.join(sorted(skip_nets))}")
        print(f"Skipped {skipped_wire_count} wire segments; {len(wires)} remain")

    wires, skipped_body_wire_count, matched_body_pin_count = base.filter_mos_body_wire_branches(
        wires,
        devices,
        instances,
        draw_mos_body_wires=args.draw_mos_b_wires,
        pin_vertex_threshold=args.pin_snap_threshold,
        placement_offsets=placement_offsets,
    )
    if not args.draw_mos_b_wires:
        print(
            "MOS B wire branch filter: "
            f"matched {matched_body_pin_count} body pin(s), "
            f"skipped {skipped_body_wire_count} wire segment(s), "
            f"{len(wires)} remain"
        )

    bounds = base.combined_bounds(instances.values(), wires, placement_offsets)
    coord = base.CoordMap(
        bounds=bounds,
        preserve_absolute=args.preserve_absolute,
        flip_y=args.flip_y,
        scale=args.scale,
    )

    print(f"Virtuoso bounds: x={bounds[0]}..{bounds[2]}, y={bounds[1]}..{bounds[3]}")
    if placement_offsets:
        print(f"Loaded {len(placement_offsets)} placement offset rule(s) from {args.placement_offsets}")
    if args.dry_run:
        print("Dry run complete; Visio was not opened")
        print("Connector mode: wires will be drawn as glued Visio dynamic connectors")
        return

    excluded_pins = {pin.strip().upper() for pin in args.exclude_pins.split(",") if pin.strip()}
    if not args.draw_mos_b_wires:
        excluded_pins.add("B")
    draw_visio_with_connectors(
        instances,
        devices,
        wires,
        args.stencil,
        coord,
        symbol_fit=args.symbol_fit,
        wire_adjust=args.wire_adjust,
        pin_snap_threshold=args.pin_snap_threshold,
        excluded_pins=excluded_pins,
        placement_offsets=placement_offsets,
        adjusted_wires_path=args.adjusted_wires_output,
        adjustment_report_path=args.adjustment_report,
        draw_nodes=args.draw_nodes,
        visible=not args.hidden,
    )


if __name__ == "__main__":
    main()
