import re
try:
    import win32com.client
except ImportError:
    win32com = None
import math
import heapq

# === 配置 ===
INPUT_FILE   = r"inst_info.txt"
NETLIST_FILE = r"netlist.txt"
STENCIL      = r"circuit.vss"  #这里要写circuit.vss的绝对路径，模具只能用这个
SCALE        = 1  # 坐标缩放倍数

# 不参与连线的网络与引脚
EXCLUDED_NETS = {}
EXCLUDED_PINS = {"B"}

# === 总线配置 ===
#这里电源和地线要改为网表中电源和地线的名称，电路没有电源和地就手动"enabled": False
BUS_NETS = {
    "VDDA": {
        "enabled": True,
        "color": "RGB(255,0,0)",
        "label": "VDDA"
    },
    "VSSA": {
        "enabled": True,  
        "color": "RGB(0,0,255)",
        "label": "VSSA"
    },
    "GNDA": {
        "enabled": False,  # 不启用该总线
        "color": "RGB(0,255,0)",
        "label": "GNDA"
    }
}

ROUTING_CONFIG = {
    "clearance": 0.10,
    "grid_margin": 1.0,
    "bend_penalty": 0.03,
    "overlap_penalty": 50.0,
    "cross_penalty": 8.0,
    "foreign_pin_penalty": 25.0,
}

EPS = 1e-6

# === 统一的器件库 ===
DEVICE_LIBRARY = {
    "NMOS": {
        "inst_prefix": ["NM", "M"],
        "netlist_prefix": ["XNM","XM"],
        "master_name": "NMOS",
        # "master_name": "NMOS_B",
        "size": (0.44, 0.59),
        "pins": {
            "D": ( 0.5,  0.5),
            "G": (-0.5, 0.0017),
            "S": ( 0.5, -0.5),
            "B": ( 0.4759,  0.0),
        }
    },
    "PMOS": {
        "inst_prefix": ["PM"],
        "netlist_prefix": ["XPM"],
        "master_name": "PMOS",
        # "master_name": "PMOS_B",
        "size": (0.44, 0.59),
        "pins": {
            "D": ( 0.5, -0.5),
            "G": (-0.5, 0.0017),
            "S": ( 0.5,  0.5),
            "B": ( 0.4759,  0.0),
        }
    },
    "RES": {
        "inst_prefix": ["R"],
        "netlist_prefix": ["XR"],
        "master_name": "R",
        "size": (0.20, 0.59),
        "pins": {
            "R_up":   (0.0,  0.5),
            "R_down": (0.0, -0.5),
        }
    },
    "Cap": {
        "inst_prefix": ["C"],
        "netlist_prefix": ["CC"],
        "master_name": "C",
        "size": (0.20, 0.59),
        "pins": {
            "C_up":   (0.0,  0.5),
            "C_down": (0.0, -0.5),
        }
    },
    # === 新增 Unknown 器件 ===
    # "UNKNOWN": {
    #     "inst_prefix": [],
    #     "netlist_prefix": [],
    #     "master_name": "Unknown",  
    #     "size": (0.43, 0.43),
    #     "pins": {
    #         "P1": (0.0, 0.5),
    #         "P2": (0.0, -0.5),
    #         "P3": (0.5, 0),
    #         "P4": (-0.5, 0),
    #         "P5": (0.0, 0)
    #     }
    # }
    # 以后你可以自己加新器件
}

def match_device_type(name, from_netlist=False):
    candidates = []
    for dev_type, cfg in DEVICE_LIBRARY.items():
        prefixes = cfg["netlist_prefix"] if from_netlist else cfg["inst_prefix"]
        for p in prefixes:
            candidates.append((len(p), p, dev_type))
    # 按前缀长度从大到小排序
    for _, p, dev_type in sorted(candidates, key=lambda x: -x[0]):
        if name.upper().startswith(p.upper()):
            return dev_type
    return "UNKNOWN"


# === 解析 inst_info.txt ===
def parse_instances(filename):
    instances = {}
    with open(filename, "r") as f:
        content = f.read()
    blocks = content.strip().split("\n\n")
    for block in blocks:
        name_m   = re.search(r"Name:\s+(\S+)", block)
        xy_m     = re.search(r"XY:\s+\((-?\d+\.?\d*)\s+(-?\d+\.?\d*)\)", block)
        orient_m = re.search(r"Orient:\s+(\S+)", block)
        if not (name_m and xy_m and orient_m):
            continue
        name   = name_m.group(1)
        x      = float(xy_m.group(1)) * SCALE
        y      = float(xy_m.group(2)) * SCALE
        orient = orient_m.group(1)

        dev_type = match_device_type(name, from_netlist=False)

        instances[name] = {
            "name": name,
            "type": dev_type,
            "xy": (x, y),
            "orient": orient
        }
    return instances

# === 解析 netlist.txt ===
def parse_netlist(filename):
    devices = []
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("*") or line.startswith("."):
                continue
            tokens = line.split()
            raw_name = tokens[0]  # e.g., CC1, CC0

            dev_type = match_device_type(raw_name, from_netlist=True)
            # 期望引脚数：来自 DEVICE_LIBRARY；未知器件则至少 2
            if dev_type in DEVICE_LIBRARY:
                pin_list = list(DEVICE_LIBRARY[dev_type]["pins"].keys())
                pin_count = len(pin_list)
            else:
                pin_count = max(2, len(tokens) - 2)  # 兜底

            if len(tokens) < 1 + pin_count:
                continue  # 行格式不足

            pins = tokens[1:1+pin_count]                # 精确按数量取引脚
            model = tokens[1+pin_count] if len(tokens) > 1+pin_count else ""  # 剩余第一个当模型/值
            # name = raw_name[1:] if raw_name.startswith("X") else raw_name
            name = raw_name[1:]
            # 对未知器件，生成 P1..Pn 引脚名；已知器件用库里的 pin 名
            if dev_type in DEVICE_LIBRARY:
                pin_names = pin_list
            else:
                pin_names = [f"P{i+1}" for i in range(pin_count)]

            pin_map = dict(zip(pin_names, pins))
            devices.append({
                "name": name,
                "type": dev_type,
                "pins": pin_map,
                "model": model
            })
    return devices

# === 放置器件 ===
def drop_with_label(page, master, inst, pin_positions, instances_map):
    dev_type = inst["type"]
    cfg = DEVICE_LIBRARY.get(dev_type, None)
    if not cfg:
        return None
    w, h = cfg["size"]
    cx, cy = inst["xy"]
    name = inst["name"]
    orient = inst["orient"]

    shp = page.Drop(master, cx, cy)
    shp.Text = name
    shp.CellsU("Width").ResultIU  = w
    shp.CellsU("Height").ResultIU = h
    # 文本位置与尺寸
    shp.CellsU("TxtPinX").ResultIU   = shp.CellsU("Width").ResultIU + 0.20
    shp.CellsU("TxtPinY").ResultIU   = shp.CellsU("Height").ResultIU / 2.0
    shp.CellsU("TxtWidth").ResultIU  = 0.6
    shp.CellsU("TxtHeight").ResultIU = 0.2


    apply_orientation(shp, orient)
    instances_map[name] = shp

    # 记录引脚坐标
    for pin in cfg["pins"]:
        pin_positions[f"{name}:{pin}"] = get_pin_position(inst, pin)

    return shp

# === 方向应用到 Visio 形状 ===
def apply_orientation(shape, orient):
    angle_map = {
        "R0": 0,
        "R90": math.pi/2,
        "R180": math.pi,
        "R270": 3*math.pi/2,
    }
    if orient in angle_map:
        shape.CellsU("Angle").ResultIU = angle_map[orient]
    elif orient == "MX":
        shape.CellsU("FlipY").FormulaU = "1"
    elif orient == "MY":
        shape.CellsU("FlipX").FormulaU = "1"
    elif orient == "MXR90":
        shape.CellsU("FlipY").FormulaU = "1"
        shape.CellsU("Angle").ResultIU = math.pi/2
    elif orient == "MYR90":
        shape.CellsU("FlipX").FormulaU = "1"
        shape.CellsU("Angle").ResultIU = math.pi/2

# === MST 构造 ===
def transform_offset(x, y, orient):
    def rotate(px, py, angle):
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return (px * cos_a - py * sin_a, px * sin_a + py * cos_a)

    if orient == "R90":
        return rotate(x, y, math.pi / 2)
    if orient == "R180":
        return rotate(x, y, math.pi)
    if orient == "R270":
        return rotate(x, y, 3 * math.pi / 2)
    if orient == "MX":
        return (x, -y)
    if orient == "MY":
        return (-x, y)
    if orient == "MXR90":
        return rotate(x, -y, math.pi / 2)
    if orient == "MYR90":
        return rotate(-x, y, math.pi / 2)
    return (x, y)

def get_pin_position(inst, pin):
    cfg = DEVICE_LIBRARY.get(inst["type"])
    if not cfg or pin not in cfg["pins"]:
        return inst["xy"]

    w, h = cfg["size"]
    rx, ry = cfg["pins"][pin]
    ox, oy = transform_offset(rx * w, ry * h, inst["orient"])
    cx, cy = inst["xy"]
    return (cx + ox, cy + oy)

def get_device_bbox(inst, padding=0.0):
    cfg = DEVICE_LIBRARY.get(inst["type"])
    if not cfg:
        x, y = inst["xy"]
        return (x - padding, y - padding, x + padding, y + padding)

    w, h = cfg["size"]
    corners = [
        (-w / 2, -h / 2),
        (-w / 2,  h / 2),
        ( w / 2, -h / 2),
        ( w / 2,  h / 2),
    ]
    transformed = [transform_offset(x, y, inst["orient"]) for x, y in corners]
    cx, cy = inst["xy"]
    xs = [cx + x for x, _ in transformed]
    ys = [cy + y for _, y in transformed]
    return (
        min(xs) - padding,
        min(ys) - padding,
        max(xs) + padding,
        max(ys) + padding,
    )

def build_mst(points, candidate_edges=None):
    if candidate_edges is None:
        candidate_edges = []
        for i, p1 in enumerate(points):
            for j, p2 in enumerate(points):
                if i < j:
                    dist = abs(p1[0]-p2[0]) + abs(p1[1]-p2[1])
                    candidate_edges.append((dist, i, j))
    candidate_edges.sort()

    parent = list(range(len(points)))
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    mst = []
    for dist, i, j in candidate_edges:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
            mst.append((points[i], points[j]))
    return mst

def norm_point(point):
    return (round(point[0], 6), round(point[1], 6))

def expand_rect(rect, padding):
    x1, y1, x2, y2 = rect
    return (x1 - padding, y1 - padding, x2 + padding, y2 + padding)

def rects_overlap(a, b, padding=0.0):
    ax1, ay1, ax2, ay2 = expand_rect(a, padding)
    bx1, by1, bx2, by2 = expand_rect(b, padding)
    return max(ax1, bx1) < min(ax2, bx2) - EPS and max(ay1, by1) < min(ay2, by2) - EPS

def report_bbox_overlaps(bboxes, limit=12):
    overlaps = []
    names = list(bboxes.keys())
    for i, name_a in enumerate(names):
        for name_b in names[i + 1:]:
            if rects_overlap(bboxes[name_a], bboxes[name_b]):
                overlaps.append((name_a, name_b))

    if overlaps:
        print(f"[Routing] Warning: {len(overlaps)} device bounding boxes overlap; routing may still touch those symbols.")
        for name_a, name_b in overlaps[:limit]:
            print(f"  - {name_a} overlaps {name_b}")
        if len(overlaps) > limit:
            print(f"  ... {len(overlaps) - limit} more")

def is_axis_segment(a, b):
    return abs(a[0] - b[0]) < EPS or abs(a[1] - b[1]) < EPS

def segment_length(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])

def segment_direction(a, b):
    if abs(a[0] - b[0]) < EPS:
        return "V"
    if abs(a[1] - b[1]) < EPS:
        return "H"
    return None

def normalized_segment(a, b):
    a = norm_point(a)
    b = norm_point(b)
    return (a, b) if a <= b else (b, a)

def unique_sorted(values):
    return sorted({round(v, 6) for v in values})

def simplify_route(route):
    compact = []
    for point in route:
        point = norm_point(point)
        if not compact or segment_length(compact[-1], point) > EPS:
            compact.append(point)

    changed = True
    while changed:
        changed = False
        reduced = []
        for point in compact:
            reduced.append(point)
            while len(reduced) >= 3:
                a, b, c = reduced[-3], reduced[-2], reduced[-1]
                if segment_direction(a, b) and segment_direction(a, b) == segment_direction(b, c):
                    reduced.pop(-2)
                    changed = True
                else:
                    break
        compact = reduced
    return compact

def segment_intersects_rect(a, b, rect):
    if not is_axis_segment(a, b):
        return False

    x1, y1 = a
    x2, y2 = b
    rx1, ry1, rx2, ry2 = rect
    xmin, xmax = min(x1, x2), max(x1, x2)
    ymin, ymax = min(y1, y2), max(y1, y2)

    if abs(y1 - y2) < EPS:
        return ry1 - EPS <= y1 <= ry2 + EPS and max(xmin, rx1) <= min(xmax, rx2) + EPS
    return rx1 - EPS <= x1 <= rx2 + EPS and max(ymin, ry1) <= min(ymax, ry2) + EPS

def segment_is_clear(a, b, bboxes, ignore_names):
    if not is_axis_segment(a, b) or segment_length(a, b) < EPS:
        return False

    clearance = ROUTING_CONFIG["clearance"]
    for name, rect in bboxes.items():
        if name in ignore_names:
            continue
        if segment_intersects_rect(a, b, expand_rect(rect, clearance)):
            return False
    return True

def point_on_segment(point, a, b, include_endpoints=False):
    px, py = point
    x1, y1 = a
    x2, y2 = b
    if abs(y1 - y2) < EPS and abs(py - y1) < EPS:
        within = min(x1, x2) - EPS <= px <= max(x1, x2) + EPS
    elif abs(x1 - x2) < EPS and abs(px - x1) < EPS:
        within = min(y1, y2) - EPS <= py <= max(y1, y2) + EPS
    else:
        return False

    if not within:
        return False
    if include_endpoints:
        return True
    return segment_length(point, a) > EPS and segment_length(point, b) > EPS

def segments_overlap(a, b, c, d):
    dir1 = segment_direction(a, b)
    dir2 = segment_direction(c, d)
    if dir1 != dir2 or dir1 is None:
        return False

    if dir1 == "H":
        if abs(a[1] - c[1]) >= EPS:
            return False
        lo = max(min(a[0], b[0]), min(c[0], d[0]))
        hi = min(max(a[0], b[0]), max(c[0], d[0]))
        return hi - lo > EPS

    if abs(a[0] - c[0]) >= EPS:
        return False
    lo = max(min(a[1], b[1]), min(c[1], d[1]))
    hi = min(max(a[1], b[1]), max(c[1], d[1]))
    return hi - lo > EPS

def segments_cross(a, b, c, d):
    dir1 = segment_direction(a, b)
    dir2 = segment_direction(c, d)
    if {dir1, dir2} != {"H", "V"}:
        return False

    h1, h2 = (a, b) if dir1 == "H" else (c, d)
    v1, v2 = (a, b) if dir1 == "V" else (c, d)
    hx1, hx2 = sorted([h1[0], h2[0]])
    vy1, vy2 = sorted([v1[1], v2[1]])
    return hx1 + EPS < v1[0] < hx2 - EPS and vy1 + EPS < h1[1] < vy2 - EPS

def segment_penalty(a, b, net, occupied_segments, point_net_map):
    penalty = 0.0
    net = net.upper()
    for owner_net, s1, s2 in occupied_segments:
        if owner_net == net:
            continue
        if segments_overlap(a, b, s1, s2):
            penalty += ROUTING_CONFIG["overlap_penalty"] * max(1.0, segment_length(a, b))
        elif segments_cross(a, b, s1, s2):
            penalty += ROUTING_CONFIG["cross_penalty"]

    for point, owner_net in point_net_map:
        if owner_net.upper() != net and point_on_segment(point, a, b):
            penalty += ROUTING_CONFIG["foreign_pin_penalty"]
    return penalty

def route_score(route, net, occupied_segments, point_net_map):
    total = 0.0
    prev_dir = None
    for a, b in zip(route, route[1:]):
        direction = segment_direction(a, b)
        if not direction:
            total += 1000.0
            continue
        total += segment_length(a, b)
        total += segment_penalty(a, b, net, occupied_segments, point_net_map)
        if prev_dir and prev_dir != direction:
            total += ROUTING_CONFIG["bend_penalty"]
        prev_dir = direction
    return total

def build_route_grid(start, end, bboxes, bounds, occupied_segments, point_net_map, ignore_names):
    clearance = ROUTING_CONFIG["clearance"]
    track_gap = max(0.01, clearance * 0.25)
    xs = {start[0], end[0], bounds[0], bounds[2], (start[0] + end[0]) / 2}
    ys = {start[1], end[1], bounds[1], bounds[3], (start[1] + end[1]) / 2}

    for name, rect in bboxes.items():
        if name in ignore_names:
            continue
        x1, y1, x2, y2 = expand_rect(rect, clearance)
        xs.update([x1 - track_gap, x2 + track_gap])
        ys.update([y1 - track_gap, y2 + track_gap])

    for _, a, b in occupied_segments:
        xs.update([a[0], b[0]])
        ys.update([a[1], b[1]])

    for point, _ in point_net_map:
        xs.add(point[0])
        ys.add(point[1])

    return unique_sorted(xs), unique_sorted(ys)

def fallback_route(start, end, bounds, bboxes, ignore_names, net, occupied_segments, point_net_map):
    x1, y1 = start
    x2, y2 = end
    candidates = [
        [start, (x1, y2), end],
        [start, (x2, y1), end],
        [start, (x1, bounds[3]), (x2, bounds[3]), end],
        [start, (x1, bounds[1]), (x2, bounds[1]), end],
        [start, (bounds[0], y1), (bounds[0], y2), end],
        [start, (bounds[2], y1), (bounds[2], y2), end],
    ]
    valid = []
    for route in candidates:
        route = simplify_route(route)
        if all(segment_is_clear(a, b, bboxes, ignore_names) for a, b in zip(route, route[1:])):
            valid.append(route)
    if not valid:
        valid = [simplify_route(candidates[0])]
    return min(valid, key=lambda r: route_score(r, net, occupied_segments, point_net_map))

def find_orthogonal_route(start, end, bboxes, bounds, ignore_names, net, occupied_segments, point_net_map):
    start = norm_point(start)
    end = norm_point(end)
    if segment_length(start, end) < EPS:
        return [start]

    xs, ys = build_route_grid(start, end, bboxes, bounds, occupied_segments, point_net_map, ignore_names)
    sx, sy = xs.index(start[0]), ys.index(start[1])
    tx, ty = xs.index(end[0]), ys.index(end[1])

    start_state = (sx, sy, "")
    dist = {start_state: 0.0}
    prev = {}
    heap = [(0.0, 0, start_state)]
    serial = 1
    end_state = None

    while heap:
        cost, _, state = heapq.heappop(heap)
        if cost > dist.get(state, float("inf")) + EPS:
            continue

        ix, iy, prev_dir = state
        if ix == tx and iy == ty:
            end_state = state
            break

        neighbors = []
        if ix > 0:
            neighbors.append((ix - 1, iy, "H"))
        if ix < len(xs) - 1:
            neighbors.append((ix + 1, iy, "H"))
        if iy > 0:
            neighbors.append((ix, iy - 1, "V"))
        if iy < len(ys) - 1:
            neighbors.append((ix, iy + 1, "V"))

        a = (xs[ix], ys[iy])
        for nx, ny, direction in neighbors:
            b = (xs[nx], ys[ny])
            if not segment_is_clear(a, b, bboxes, ignore_names):
                continue

            step = segment_length(a, b)
            step += segment_penalty(a, b, net, occupied_segments, point_net_map)
            if prev_dir and prev_dir != direction:
                step += ROUTING_CONFIG["bend_penalty"]

            next_state = (nx, ny, direction)
            next_cost = cost + step
            if next_cost + EPS < dist.get(next_state, float("inf")):
                dist[next_state] = next_cost
                prev[next_state] = state
                heapq.heappush(heap, (next_cost, serial, next_state))
                serial += 1

    if end_state is None:
        return fallback_route(start, end, bounds, bboxes, ignore_names, net, occupied_segments, point_net_map)

    route = []
    state = end_state
    while True:
        ix, iy, _ = state
        route.append((xs[ix], ys[iy]))
        if state == start_state:
            break
        state = prev[state]
    route.reverse()
    return simplify_route(route)

def build_mst_indices(count, candidate_edges):
    parent = list(range(count))

    def find(value):
        while parent[value] != value:
            parent[value] = parent[parent[value]]
            value = parent[value]
        return value

    selected = []
    for cost, i, j in sorted(candidate_edges):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj
            selected.append((i, j))
    return selected

def build_routed_mst(pins, net, bboxes, bounds, occupied_segments, point_net_map):
    candidate_edges = []
    route_by_edge = {}
    for i, pin_a in enumerate(pins):
        for j, pin_b in enumerate(pins):
            if i >= j:
                continue
            ignore_names = {pin_a[0], pin_b[0]}
            route = find_orthogonal_route(
                pin_a[3],
                pin_b[3],
                bboxes,
                bounds,
                ignore_names,
                net,
                occupied_segments,
                point_net_map,
            )
            cost = route_score(route, net, occupied_segments, point_net_map)
            candidate_edges.append((cost, i, j))
            route_by_edge[(i, j)] = route

    selected = build_mst_indices(len(pins), candidate_edges)
    return [(pins[i], pins[j], route_by_edge[(min(i, j), max(i, j))]) for i, j in selected]

def glue_shape_pin(line, end_name, dev, dtype, pin, instances_map):
    if not dev or dtype not in DEVICE_LIBRARY:
        return
    shape = instances_map.get(dev)
    if not shape:
        return

    pin_list = list(DEVICE_LIBRARY[dtype]["pins"].keys())
    if pin not in pin_list:
        return

    idx = pin_list.index(pin) + 1
    try:
        conn_x = shape.CellsU(f"Connections.X{idx}")
        conn_y = shape.CellsU(f"Connections.Y{idx}")
        line.CellsU(f"{end_name}X").GlueTo(conn_x)
        line.CellsU(f"{end_name}Y").GlueTo(conn_y)
    except Exception as e:
        print(f"[Glue] {dev}:{pin} failed: {e}")

def glue_bus_tap(line, end_name, bus_line, row):
    try:
        conn_x = bus_line.CellsSRC(10, row, 0)
        conn_y = bus_line.CellsSRC(10, row, 1)
        line.CellsU(f"{end_name}X").GlueTo(conn_x)
        line.CellsU(f"{end_name}Y").GlueTo(conn_y)
    except Exception as e:
        print(f"[Glue] bus tap failed: {e}")

def draw_route(page, route, net, instances_map, occupied_segments, drawn_segments,
               begin_pin=None, end_pin=None, end_bus=None, color=None):
    route = simplify_route(route)
    if len(route) < 2:
        return

    segments = [(a, b) for a, b in zip(route, route[1:]) if segment_length(a, b) > EPS]
    for index, (a, b) in enumerate(segments):
        key = (net.upper(), normalized_segment(a, b))
        if key in drawn_segments:
            continue

        line = page.DrawLine(a[0], a[1], b[0], b[1])
        line.CellsU("ConFixedCode").FormulaU = "3"
        line.CellsU("LineWeight").FormulaU = "1.2 pt"
        line.CellsU("LinePattern").FormulaU = "1"
        if color:
            line.CellsU("LineColor").FormulaU = color

        if index == 0 and begin_pin:
            glue_shape_pin(line, "Begin", begin_pin[0], begin_pin[1], begin_pin[2], instances_map)
        if index == len(segments) - 1:
            if end_pin:
                glue_shape_pin(line, "End", end_pin[0], end_pin[1], end_pin[2], instances_map)
            if end_bus:
                glue_bus_tap(line, "End", end_bus[0], end_bus[1])

        drawn_segments.add(key)
        occupied_segments.append((net.upper(), norm_point(a), norm_point(b)))


def draw_net_lines_v2_legacy(page, netlist, pin_positions, instances_map, bboxes):
    if not bboxes:
        return

    # 1) 计算器件全局边界
    min_x = min(x1 for (x1, y1, x2, y2) in bboxes.values())
    max_x = max(x2 for (x1, y1, x2, y2) in bboxes.values())
    min_y = min(y1 for (x1, y1, x2, y2) in bboxes.values())
    max_y = max(y2 for (x1, y1, x2, y2) in bboxes.values())

    margin_x = 1.0
    margin_y = 1.0
    bus_left  = min_x - margin_x
    bus_right = max_x + margin_x

    # 2) 绘制总线（由 BUS_NETS 配置驱动）
    bus_lines = {}
    offset = 0
    for net_name, cfg in BUS_NETS.items():
        if not cfg.get("enabled", True):  # 默认启用，除非显式设置为 False
            continue

        label = cfg.get("label", net_name)
        color = cfg.get("color", "RGB(0,0,0)")

        # 简单规则：第一个放在上边，第二个放在下边，其他依次往下排
        if offset == 0:
            y = max_y + margin_y
        elif offset == 1:
            y = min_y - margin_y
        else:
            y = min_y - margin_y - (offset - 1) * 0.1

        line = page.DrawLine(bus_left, y, bus_right, y)
        line.Text = label
        line.CellsU("LineWeight").FormulaU = "2 pt"
        line.CellsU("LineColor").FormulaU  = color
        line.CellsU("TxtPinX").FormulaU = "0"
        line.CellsU("TxtPinY").FormulaU = "Height*0.5"

        bus_lines[net_name.upper()] = line
        offset += 1

    # 3) 收集网络点
    net_to_points = {}
    for dev in netlist:
        name = dev["name"]
        dev_type = dev["type"]
        for pin, net in dev["pins"].items():
            if pin.upper() in EXCLUDED_PINS or net.upper() in EXCLUDED_NETS:
                continue
            key = f"{name}:{pin}"
            if key in pin_positions:
                pt = pin_positions[key]
                net_to_points.setdefault(net, []).append((name, dev_type, pin, pt))

    # 4) 绘制连线
    for net, pins in net_to_points.items():
        if len(pins) < 1:
            continue

        net_upper = net.upper()
        # === 特殊处理：如果是总线 ===
        if net_upper in bus_lines:
            bus_line = bus_lines[net_upper]
            for (dev, dtype, pin, pt) in pins:
                # 在总线上添加一个连接点
                sec = 10  # visSectionConnectionPts
                row = bus_line.AddRow(sec, -1, 0)
                bus_line.CellsSRC(sec, row, 0).ResultIU = pt[0] - bus_left
                bus_line.CellsSRC(sec, row, 1).ResultIU = 0
                bus_line.CellsSRC(sec, row, 2).FormulaU = "1"

                # 创建竖线（只 Glue，不设坐标）
                line = page.Drop(page.Application.ConnectorToolDataObject, 0, 0)
                line.CellsU("ConFixedCode").FormulaU = "3"
                line.CellsU("LineWeight").FormulaU = "1.2 pt"

                # Glue 器件端
                if dev and dtype in DEVICE_LIBRARY:
                    shape = instances_map.get(dev)
                    if shape:
                        pin_list = list(DEVICE_LIBRARY[dtype]["pins"].keys())
                        if pin in pin_list:
                            idx = pin_list.index(pin) + 1
                            try:
                                conn_x = shape.CellsU(f"Connections.X{idx}")
                                conn_y = shape.CellsU(f"Connections.Y{idx}")
                                line.CellsU("BeginX").GlueTo(conn_x)
                                line.CellsU("BeginY").GlueTo(conn_y)
                            except Exception as e:
                                print(f"[Glue] {dev}:{pin} 失败: {e}")

                # Glue 总线端
                try:
                    conn_x = bus_line.CellsSRC(sec, row, 0)
                    conn_y = bus_line.CellsSRC(sec, row, 1)
                    line.CellsU("EndX").GlueTo(conn_x)
                    line.CellsU("EndY").GlueTo(conn_y)
                except Exception as e:
                    print(f"[Glue] {net_upper} 总线端失败: {e}")
            continue

        # === 普通网络：MST ===
        if len(pins) < 2:
            continue
        coords = [pt for _, _, _, pt in pins]
        edges = build_mst(coords)

        for p1, p2 in edges:
            horiz = abs(p1[1]-p2[1]) < 1e-6
            vert  = abs(p1[0]-p2[0]) < 1e-6

            # line = page.Drop(page.Application.ConnectorToolDataObject, 0, 0)
            line = page.DrawLine(p1[0], p1[1], p2[0], p2[1])
            line.CellsU("ConFixedCode").FormulaU = "3"
            line.CellsU("LineWeight").FormulaU = "1.2 pt"

            if horiz or vert:
                line.CellsU("RouteStyle").FormulaU = "16"  # Straight
                line.CellsU("LinePattern").FormulaU = "1"   # 实线
            else:
                line.CellsU("RouteStyle").FormulaU = "64"  # Orthogonal
                line.CellsU("LinePattern").FormulaU = "2"   # 虚线

            # 自动 GlueTo
            def find_dev_pin(pt, pins, tol=1e-4):
                tx, ty = pt
                for (dn, dt, pn, (x, y)) in pins:
                    if abs(x - tx) < tol and abs(y - ty) < tol:
                        return dn, dt, pn
                return None, None, None

            dev1, type1, pin1 = find_dev_pin(p1, pins)
            dev2, type2, pin2 = find_dev_pin(p2, pins)

            for dev, dtype, pin, end in [(dev1, type1, pin1, "Begin"),
                                         (dev2, type2, pin2, "End")]:
                if dev and dtype in DEVICE_LIBRARY:
                    shape = instances_map.get(dev)
                    if shape:
                        pin_list = list(DEVICE_LIBRARY[dtype]["pins"].keys())
                        if pin in pin_list:
                            idx = pin_list.index(pin) + 1
                            try:
                                conn_x = shape.CellsU(f"Connections.X{idx}")
                                conn_y = shape.CellsU(f"Connections.Y{idx}")
                                line.CellsU(f"{end}X").GlueTo(conn_x)
                                line.CellsU(f"{end}Y").GlueTo(conn_y)
                            except Exception as e:
                                print(f"[Glue] {dev}:{pin} 失败: {e}")


# === 主程序 ===
def draw_net_lines(page, netlist, pin_positions, instances_map, bboxes):
    if not bboxes:
        return

    min_x = min(x1 for (x1, y1, x2, y2) in bboxes.values())
    max_x = max(x2 for (x1, y1, x2, y2) in bboxes.values())
    min_y = min(y1 for (x1, y1, x2, y2) in bboxes.values())
    max_y = max(y2 for (x1, y1, x2, y2) in bboxes.values())

    margin_x = ROUTING_CONFIG["grid_margin"]
    margin_y = ROUTING_CONFIG["grid_margin"]
    bus_left = min_x - margin_x
    bus_right = max_x + margin_x

    net_to_points = {}
    for dev in netlist:
        name = dev["name"]
        dev_type = dev["type"]
        for pin, net in dev["pins"].items():
            if pin.upper() in EXCLUDED_PINS or net.upper() in EXCLUDED_NETS:
                continue
            key = f"{name}:{pin}"
            if key in pin_positions:
                pt = norm_point(pin_positions[key])
                net_to_points.setdefault(net, []).append((name, dev_type, pin, pt))

    point_net_map = []
    for net, pins in net_to_points.items():
        for _, _, _, point in pins:
            point_net_map.append((point, net))

    bus_lines = {}
    offset = 0
    for net_name, cfg in BUS_NETS.items():
        if not cfg.get("enabled", True):
            continue

        label = cfg.get("label", net_name)
        color = cfg.get("color", "RGB(0,0,0)")
        if offset == 0:
            y = max_y + margin_y
        elif offset == 1:
            y = min_y - margin_y
        else:
            y = min_y - margin_y - (offset - 1) * 0.25

        line = page.DrawLine(bus_left, y, bus_right, y)
        line.Text = label
        line.CellsU("LineWeight").FormulaU = "2 pt"
        line.CellsU("LineColor").FormulaU = color
        line.CellsU("TxtPinX").FormulaU = "0"
        line.CellsU("TxtPinY").FormulaU = "Height*0.5"
        bus_lines[net_name.upper()] = {"shape": line, "y": y, "color": color}
        offset += 1

    bus_ys = [item["y"] for item in bus_lines.values()]
    route_min_y = min([min_y - margin_y] + bus_ys) - margin_y
    route_max_y = max([max_y + margin_y] + bus_ys) + margin_y
    bounds = (bus_left - margin_x, route_min_y, bus_right + margin_x, route_max_y)

    occupied_segments = []
    drawn_segments = set()

    for net, pins in net_to_points.items():
        if len(pins) < 1:
            continue

        net_upper = net.upper()
        if net_upper in bus_lines:
            bus_info = bus_lines[net_upper]
            bus_line = bus_info["shape"]
            bus_y = bus_info["y"]
            for dev, dtype, pin, pt in pins:
                target = norm_point((pt[0], bus_y))
                sec = 10
                row = bus_line.AddRow(sec, -1, 0)
                bus_line.CellsSRC(sec, row, 0).ResultIU = target[0] - bus_left
                bus_line.CellsSRC(sec, row, 1).ResultIU = 0
                bus_line.CellsSRC(sec, row, 2).FormulaU = "1"

                route = find_orthogonal_route(
                    pt,
                    target,
                    bboxes,
                    bounds,
                    {dev},
                    net,
                    occupied_segments,
                    point_net_map,
                )
                draw_route(
                    page,
                    route,
                    net,
                    instances_map,
                    occupied_segments,
                    drawn_segments,
                    begin_pin=(dev, dtype, pin),
                    end_bus=(bus_line, row),
                    color=bus_info["color"],
                )
            continue

        if len(pins) < 2:
            continue

        routed_edges = build_routed_mst(
            pins,
            net,
            bboxes,
            bounds,
            occupied_segments,
            point_net_map,
        )
        for pin_a, pin_b, route in routed_edges:
            draw_route(
                page,
                route,
                net,
                instances_map,
                occupied_segments,
                drawn_segments,
                begin_pin=(pin_a[0], pin_a[1], pin_a[2]),
                end_pin=(pin_b[0], pin_b[1], pin_b[2]),
            )

def main():
    if win32com is None:
        raise RuntimeError("pywin32 is required to drive Microsoft Visio. Install it with: pip install pywin32")

    # 启动 Visio
    visio = win32com.client.Dispatch("Visio.Application")
    visio.Visible = True
    doc = visio.Documents.Add("")
    page = visio.ActivePage

    # 打开模具库
    stencil = visio.Documents.OpenEx(STENCIL, 64)
    # 根据 DEVICE_LIBRARY 里的 master_name 建立映射
    masters = {}
    for dev_type, cfg in DEVICE_LIBRARY.items():
        try:
            masters[dev_type] = stencil.Masters(cfg["master_name"])
        except Exception as e:
            print(f"[警告] 模具 {cfg['master_name']} 未找到: {e}")

    # 解析输入文件
    instances = parse_instances(INPUT_FILE)
    netlist   = parse_netlist(NETLIST_FILE)

    pin_positions = {}
    bboxes = {}
    shapes_map = {}

    # 放置器件
    for inst in instances.values():
        dev_type = inst["type"]
        cfg = DEVICE_LIBRARY.get(dev_type, None)
        if not cfg or dev_type not in masters:
            continue
        master = masters[dev_type]
        shp = drop_with_label(page, master, inst, pin_positions, shapes_map)
        if shp:
            bboxes[inst["name"]] = get_device_bbox(inst)
    report_bbox_overlaps(bboxes)
    print("\n✅ 所有器件已放置完成")
    print("➡️  开始自动连线...")

    draw_net_lines(page, netlist, pin_positions, shapes_map, bboxes)

    print("✅ 连线完成")

    # === 交互式处理虚线 ===
    choice = input("\n是否将剩余虚线改为粗实线？ [Y/N]: ").strip().lower()
    if choice == "y":
        modified = 0
        for shape in page.Shapes:
            try:
                if shape.OneD and shape.CellExistsU("LinePattern", 0):
                    if int(shape.CellsU("LinePattern").ResultIU) == 2:  # 虚线
                        shape.CellsU("LinePattern").FormulaU = "1"   # 改为实线
                        shape.CellsU("LineWeight").FormulaU = "1.2 pt"
                        modified += 1
            except Exception:
                pass
        print(f"✨ 已将 {modified} 条虚线改为实线")
    else:
        print("⚡ 保留虚线，不做修改")



if __name__ == "__main__":
    main()
