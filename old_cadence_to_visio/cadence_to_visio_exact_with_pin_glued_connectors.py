"""Draw wires as Visio connectors, glued directly to device pins when possible.

This script does not modify the original drawing scripts. It reuses their
parsing, placement, MOS-B filtering, and connector helpers, but changes the
wire endpoint target selection:

* if a wire endpoint matches a same-net device pin, glue to Connections.Xn/Yn;
* otherwise, glue to a hidden endpoint anchor.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Set, Tuple

import cadence_to_visio_exact_from_wires as base
import cadence_to_visio_exact_with_connectors as conn


Point = Tuple[float, float]
EndpointKey = Tuple[str, Point]
PIN_DIRECT_GLUE_EPS = base.PIN_ADAPTER_EPS


@dataclass
class PinGlueInfo:
    target: conn.GlueTarget
    inst_name: str
    pin: str
    net: str
    virt_point: Point
    page_point: Point
    distance: float


@dataclass
class PinGlueCandidate:
    inst_name: str
    pin: str
    net: str
    shape: object
    conn_idx: int
    virt_point: Point
    page_point: Point


def collect_pin_glue_candidates(
    page,
    devices: Sequence[base.NetDevice],
    instances: Dict[str, base.Instance],
    shapes: Dict[str, object],
    coord: base.CoordMap,
    excluded_pins: Set[str],
) -> Dict[str, List[PinGlueCandidate]]:
    candidates_by_net: Dict[str, List[PinGlueCandidate]] = {}

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
            page_point = base.connection_page_point(page, shape, conn_idx)
            if page_point is None:
                continue

            candidate = PinGlueCandidate(
                inst_name=device.name,
                pin=pin,
                net=net,
                shape=shape,
                conn_idx=conn_idx,
                virt_point=coord.inverse_point(page_point),
                page_point=page_point,
            )
            candidates_by_net.setdefault(base.normalize_net(net), []).append(candidate)

    return candidates_by_net


def unique_wire_endpoints(wires: Sequence[base.WireSegment]) -> Dict[EndpointKey, Point]:
    endpoints: Dict[EndpointKey, Point] = {}
    for segment in wires:
        for point in (segment.p1, segment.p2):
            endpoints[conn.endpoint_key(segment, point)] = point
    return endpoints


def build_endpoint_pin_targets(
    page,
    devices: Sequence[base.NetDevice],
    instances: Dict[str, base.Instance],
    shapes: Dict[str, object],
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
    threshold: float,
    excluded_pins: Set[str],
) -> Tuple[Dict[EndpointKey, PinGlueInfo], int]:
    candidates_by_net = collect_pin_glue_candidates(
        page,
        devices,
        instances,
        shapes,
        coord,
        excluded_pins,
    )
    targets: Dict[EndpointKey, PinGlueInfo] = {}
    skipped_noncoincident = 0

    for endpoint_key, endpoint_point in unique_wire_endpoints(wires).items():
        net_key, _point_key = endpoint_key
        candidates = candidates_by_net.get(net_key, [])
        if not candidates:
            continue

        best = min(candidates, key=lambda candidate: base.distance_sq(endpoint_point, candidate.virt_point))
        distance = math.sqrt(base.distance_sq(endpoint_point, best.virt_point))
        if distance > threshold:
            continue
        if distance > PIN_DIRECT_GLUE_EPS:
            skipped_noncoincident += 1
            continue

        targets[endpoint_key] = PinGlueInfo(
            target=conn.GlueTarget(best.shape, best.conn_idx),
            inst_name=best.inst_name,
            pin=best.pin,
            net=best.net,
            virt_point=best.virt_point,
            page_point=best.page_point,
            distance=distance,
        )

    return targets, skipped_noncoincident


def target_for_wire_endpoint(
    page,
    anchors: Dict[EndpointKey, object],
    pin_targets: Dict[EndpointKey, PinGlueInfo],
    segment: base.WireSegment,
    virt_point: Point,
    page_point: Point,
) -> conn.GlueTarget:
    key = conn.endpoint_key(segment, virt_point)
    pin_target = pin_targets.get(key)
    if pin_target is not None:
        return pin_target.target

    anchor = conn.ensure_anchor(page, anchors, key, page_point)
    return conn.GlueTarget(anchor)


def format_exact_wire_segment(line, weight: str = base.WIRE_WEIGHT) -> None:
    line.Text = ""
    conn.set_formula(line, "LineWeight", weight)
    conn.set_formula(line, "LineColor", base.WIRE_COLOR)
    conn.set_formula(line, "LinePattern", "1")
    conn.set_formula(line, "BeginArrow", "0")
    conn.set_formula(line, "EndArrow", "0")


def draw_exact_glued_wire_segment(
    page,
    begin: Point,
    end: Point,
    begin_target: conn.GlueTarget,
    end_target: conn.GlueTarget,
    weight: str = base.WIRE_WEIGHT,
) -> Tuple[object, int]:
    line = page.DrawLine(begin[0], begin[1], end[0], end[1])
    format_exact_wire_segment(line, weight)
    glue_failures = 0
    if not conn.glue_endpoint_to_target(line, "Begin", begin_target):
        glue_failures += 1
    if not conn.glue_endpoint_to_target(line, "End", end_target):
        glue_failures += 1
    try:
        line.SendToBack()
    except Exception:
        pass
    return line, glue_failures


def draw_wire_connectors_with_pin_targets(
    visio,
    page,
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
    pin_targets: Dict[EndpointKey, PinGlueInfo],
) -> Tuple[Dict[EndpointKey, object], int, int]:
    anchors: Dict[EndpointKey, object] = {}
    connector_count = 0
    glue_failures = 0

    for segment in wires:
        p1 = coord.point(segment.p1)
        p2 = coord.point(segment.p2)
        begin_target = target_for_wire_endpoint(page, anchors, pin_targets, segment, segment.p1, p1)
        end_target = target_for_wire_endpoint(page, anchors, pin_targets, segment, segment.p2, p2)
        _connector, failures = draw_exact_glued_wire_segment(
            page,
            p1,
            p2,
            begin_target,
            end_target,
        )
        connector_count += 1
        glue_failures += failures

    return anchors, connector_count, glue_failures


def glue_shape_center_to_target(shape, target: conn.GlueTarget) -> bool:
    if target.conn_idx is not None:
        try:
            shape.CellsU("PinX").GlueTo(target.shape.CellsU(f"Connections.X{target.conn_idx}"))
            shape.CellsU("PinY").GlueTo(target.shape.CellsU(f"Connections.Y{target.conn_idx}"))
            return True
        except Exception:
            pass

    try:
        shape.CellsU("PinX").GlueTo(target.shape.CellsU("PinX"))
        shape.CellsU("PinY").GlueTo(target.shape.CellsU("PinY"))
        return True
    except Exception:
        pass

    try:
        shape.CellsU("PinX").GlueToPos(target.shape, 0.5, 0.5)
        return True
    except Exception:
        return False


def t_junction_vertex_keys(wires: Sequence[base.WireSegment]) -> List[EndpointKey]:
    wire_lookup, endpoint_to_segments = base.build_wire_graph_by_net(wires)
    return sorted(
        (
            vertex_key
            for vertex_key in endpoint_to_segments
            if base.is_t_junction_vertex(vertex_key, wire_lookup, endpoint_to_segments)
        ),
        key=lambda item: (item[0], item[1][0], item[1][1]),
    )


def draw_attached_t_junction_nodes(
    page,
    master_index: Dict[str, object],
    wires: Sequence[base.WireSegment],
    coord: base.CoordMap,
    anchors: Dict[EndpointKey, object],
    pin_targets: Dict[EndpointKey, PinGlueInfo],
) -> Tuple[int, int]:
    node_count = 0
    glue_failures = 0

    for vertex_key in t_junction_vertex_keys(wires):
        net_key, point = vertex_key
        page_point = coord.point(point)
        pin_target = pin_targets.get(vertex_key)
        if pin_target is not None:
            target = pin_target.target
        else:
            anchor = conn.ensure_anchor(page, anchors, (net_key, point), page_point)
            target = conn.GlueTarget(anchor)

        node = base.draw_node(page, master_index, coord, point)
        if not glue_shape_center_to_target(node, target):
            glue_failures += 1
        node_count += 1

    return node_count, glue_failures


def draw_unmatched_pin_adapters_as_connectors(
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
    matched_pin_refs: Set[Tuple[str, str]],
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
            if (device.name, pin) in matched_pin_refs:
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
            wire_anchor = conn.ensure_anchor(page, anchors, wire_key, end)
            count, failures = conn.draw_orthogonal_adapter_connectors(
                visio,
                page,
                anchors,
                start,
                end,
                conn.GlueTarget(shape, conn_idx),
                conn.GlueTarget(wire_anchor),
            )
            adapter_count += count
            glue_failures += failures

    return adapter_count, glue_failures


def draw_visio_with_pin_glued_connectors(
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

    pin_targets, skipped_noncoincident_pin_count = build_endpoint_pin_targets(
        page,
        devices,
        instances,
        shapes,
        wires,
        coord,
        pin_snap_threshold,
        excluded_pins,
    )
    anchors, connector_count, glue_failures = draw_wire_connectors_with_pin_targets(
        visio,
        page,
        wires,
        coord,
        pin_targets,
    )
    if draw_nodes:
        node_count, node_glue_failures = draw_attached_t_junction_nodes(
            page,
            master_index,
            wires,
            coord,
            anchors,
            pin_targets,
        )
    else:
        node_count = 0
        node_glue_failures = 0

    adapter_count = 0
    adapter_glue_failures = 0
    if wire_adjust == "adapters":
        matched_pin_refs = {(info.inst_name, info.pin) for info in pin_targets.values()}
        adapter_count, adapter_glue_failures = draw_unmatched_pin_adapters_as_connectors(
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
            matched_pin_refs,
        )

    conn.bring_devices_to_front(shapes)
    label_count = conn.draw_device_labels(page, instances, shapes)

    total_glue_failures = glue_failures + adapter_glue_failures + node_glue_failures
    print(f"Drew {len(instances)} instances and {connector_count} exact glued wire segment(s)")
    print(f"Directly glued {len(pin_targets)} wire endpoint(s) to device connection point(s)")
    print(f"Skipped {skipped_noncoincident_pin_count} near pin target(s) to preserve original wire endpoint coordinates")
    print(f"Created {len(anchors)} shared endpoint/junction anchor(s); glue failures: {total_glue_failures}")
    if draw_nodes:
        print(f"Added and attached {node_count} T-junction node(s); added {label_count} device label(s)")
    else:
        print(f"Skipped T-junction nodes; added {label_count} device label(s)")
    if wire_adjust == "snap-endpoints":
        print(f"Found {dangling_count} dangling wire endpoints; snapped {len(adjustments)}")
        print(f"Wrote adjusted wires to {adjusted_wires_path}")
        print(f"Wrote adjustment report to {adjustment_report_path}")
    if wire_adjust == "adapters":
        print(f"Added {adapter_count} unmatched-pin adapter connector segment(s)")


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
        print("Pin-glued exact segment mode: coincident wire endpoints will glue directly to device Connections.Xn/Yn")
        return

    excluded_pins = {pin.strip().upper() for pin in args.exclude_pins.split(",") if pin.strip()}
    if not args.draw_mos_b_wires:
        excluded_pins.add("B")
    draw_visio_with_pin_glued_connectors(
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
