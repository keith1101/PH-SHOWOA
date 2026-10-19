from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple, Union


@dataclass
class Node:
    id: int
    x: float
    y: float
    delivery: float
    pickup: float
    ready: float
    due: float
    service: float


CANONICAL_INSTANCES = {
    # 9 small
    "rcdp1001": "RCdp1001", "rcdp1004": "RCdp1004", "rcdp1007": "RCdp1007",
    "rcdp2501": "RCdp2501", "rcdp2504": "RCdp2504", "rcdp2507": "RCdp2507",
    "rcdp5001": "RCdp5001", "rcdp5004": "RCdp5004", "rcdp5007": "RCdp5007",
    "rcdp0501": "RCdp5001", "rcdp0504": "RCdp5004", "rcdp0507": "RCdp5007",
    # 56 medium
    "rcdp101": "RCdp101", "rcdp102": "RCdp102", "rcdp103": "RCdp103", "rcdp104": "RCdp104",
    "rcdp105": "RCdp105", "rcdp106": "RCdp106", "rcdp107": "RCdp107", "rcdp108": "RCdp108",
    "rcdp201": "RCdp201", "rcdp202": "RCdp202", "rcdp203": "RCdp203", "rcdp204": "RCdp204",
    "rcdp205": "RCdp205", "rcdp206": "RCdp206", "rcdp207": "RCdp207", "rcdp208": "RCdp208",
    "cdp101": "Cdp101", "cdp102": "Cdp102", "cdp103": "Cdp103", "cdp104": "Cdp104",
    "cdp105": "Cdp105", "cdp106": "Cdp106", "cdp107": "Cdp107", "cdp108": "Cdp108", "cdp109": "Cdp109",
    "cdp201": "Cdp201", "cdp202": "Cdp202", "cdp203": "Cdp203", "cdp204": "Cdp204",
    "cdp205": "Cdp205", "cdp206": "Cdp206", "cdp207": "Cdp207", "cdp208": "Cdp208",
    "rdp101": "Rdp101", "rdp102": "Rdp102", "rdp103": "Rdp103", "rdp104": "Rdp104",
    "rdp105": "Rdp105", "rdp106": "Rdp106", "rdp107": "Rdp107", "rdp108": "Rdp108",
    "rdp109": "Rdp109", "rdp110": "Rdp110", "rdp111": "Rdp111", "rdp112": "Rdp112",
    "rdp201": "Rdp201", "rdp202": "Rdp202", "rdp203": "Rdp203", "rdp204": "Rdp204",
    "rdp205": "Rdp205", "rdp206": "Rdp206", "rdp207": "Rdp207", "rdp208": "Rdp208",
    "rdp209": "Rdp209", "rdp210": "Rdp210", "rdp211": "Rdp211",
}


def normalize_instance_name(raw: str) -> str:
    cleaned = raw.strip()
    if cleaned.lower().startswith("explicit_"):
        cleaned = cleaned[9:]
    for ext in [".txt", ".vrpsdptw"]:
        if cleaned.lower().endswith(ext):
            cleaned = cleaned[:-len(ext)]
    return CANONICAL_INSTANCES.get(cleaned.lower(), raw)


class Problem:
    def __init__(
        self,
        name: str,
        nodes: List[Node],
        distance: List[List[float]],
        travel_time: List[List[float]],
        max_vehicles: int,
        capacity: float,
        dispatch_cost: float = 2000.0,
        unit_cost: float = 1.0,
    ) -> None:
        self.name = normalize_instance_name(name)
        self.nodes = nodes
        self.num_customers = len(nodes) - 1
        self.distance = distance
        self.travel_time = travel_time
        self.max_vehicles = max_vehicles
        self.capacity = capacity
        self.dispatch_cost = dispatch_cost
        self.unit_cost = unit_cost

        # Convenient lookup arrays
        self.delivery = [n.delivery for n in nodes]
        self.pickup = [n.pickup for n in nodes]
        self.ready_time = [n.ready for n in nodes]
        self.due_time = [n.due for n in nodes]
        self.service_time = [n.service for n in nodes]

    @classmethod
    def load(cls, path_or_str: Union[str, Path]) -> Problem:
        path = Path(path_or_str)
        if not path.is_file():
            raise FileNotFoundError(f"Instance file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        # Detect format: explicit VRPSDPTW or Wang-Chen / Solomon .txt
        is_explicit = any(
            line.upper().startswith("DIMENSION")
            or line.upper().startswith("NODE_SECTION")
            or "DISTANCETIME_SECTION" in line.upper()
            for line in lines[:20]
        )
        if is_explicit:
            return cls._load_explicit(path.stem, lines)
        else:
            return cls._load_txt(path.stem, lines)

    @classmethod
    def _load_txt(cls, stem: str, lines: List[str]) -> Problem:
        name = stem
        customer_count = -1
        vehicles = 100
        capacity = 200.0
        nodes: List[Node] = []
        points: List[Tuple[float, float]] = []

        coordinates_mode = False
        i = 0
        while i < len(lines):
            line = lines[i]
            upper = line.upper()
            if upper.startswith("CUSTOMER") and "VEHICLE" in upper:
                i += 1
                continue
            if upper.startswith("NUMBER") and "CAPACITY" in upper:
                i += 1
                continue
            if not coordinates_mode:
                if upper.startswith("CUST") and "XCOORD" in upper:
                    coordinates_mode = True
                    i += 1
                    continue
                parts = line.split()
                if len(parts) == 3:
                    customer_count = int(parts[0])
                    vehicles = int(parts[1])
                    capacity = float(parts[2])
                elif len(parts) == 2:
                    vehicles = int(parts[0])
                    capacity = float(parts[1])
                i += 1
            else:
                parts = [p for p in re.split(r"[,\s]+", line) if p]
                if len(parts) >= 8:
                    cid = int(parts[0])
                    x = float(parts[1])
                    y = float(parts[2])
                    d = float(parts[3])
                    p = float(parts[4])
                    ready = float(parts[5])
                    due = float(parts[6])
                    service = float(parts[7])
                    nodes.append(Node(cid, x, y, d, p, ready, due, service))
                    points.append((x, y))
                i += 1

        if not nodes:
            raise ValueError(f"No customer nodes parsed from {stem}")

        # Compute Euclidean distance matrix
        n = len(nodes)
        distance = [[0.0] * n for _ in range(n)]
        for u in range(n):
            for v in range(n):
                if u != v:
                    dx = points[u][0] - points[v][0]
                    dy = points[u][1] - points[v][1]
                    dist = math.hypot(dx, dy)
                    distance[u][v] = dist

        # In Wang & Chen benchmark, travel time = Euclidean distance at unit speed
        travel_time = [row[:] for row in distance]

        return cls(
            name=name,
            nodes=nodes,
            distance=distance,
            travel_time=travel_time,
            max_vehicles=vehicles,
            capacity=capacity,
            dispatch_cost=2000.0,
            unit_cost=1.0,
        )

    @classmethod
    def _load_explicit(cls, stem: str, lines: List[str]) -> Problem:
        name = stem
        dimension = 0
        vehicles = 100
        capacity = 200.0
        dispatch_cost = 2000.0
        unit_cost = 1.0

        nodes: List[Node] = []
        section = 0  # 0: header, 1: nodes, 2: distance/time, 3: depot
        raw_nodes: dict[int, Node] = {}
        distance: List[List[float]] = []
        travel_time: List[List[float]] = []
        node_indices: dict[int, int] = {}

        for line in lines:
            upper = line.upper()
            if upper == "EOF":
                break
            if upper.startswith("NAME"):
                parts = line.split(":")
                if len(parts) > 1:
                    name = parts[1].strip()
            elif upper.startswith("DIMENSION"):
                dimension = int(line.split(":")[1].strip())
            elif upper.startswith("VEHICLES"):
                vehicles = int(line.split(":")[1].strip())
            elif upper.startswith("CAPACITY"):
                capacity = float(line.split(":")[1].strip())
            elif upper.startswith("DISPATCHINGCOST"):
                dispatch_cost = float(line.split(":")[1].strip())
            elif upper.startswith("UNITCOST"):
                unit_cost = float(line.split(":")[1].strip())
            elif upper.startswith("NODE_SECTION"):
                section = 1
                continue
            elif upper.startswith("DISTANCETIME_SECTION"):
                section = 2
                distance = [[0.0] * dimension for _ in range(dimension)]
                travel_time = [[0.0] * dimension for _ in range(dimension)]
                continue
            elif upper.startswith("DEPOT_SECTION"):
                section = 3
                continue

            if section == 1:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 6:
                    cid = int(parts[0])
                    d = float(parts[1])
                    p = float(parts[2])
                    ready = float(parts[3])
                    due = float(parts[4])
                    service = float(parts[5])
                    raw_nodes[cid] = Node(cid, 0.0, 0.0, d, p, ready, due, service)
            elif section == 2:
                parts = [p.strip() for p in line.split(",") if p.strip()]
                if len(parts) >= 4:
                    u_id = int(parts[0])
                    v_id = int(parts[1])
                    d_val = float(parts[2])
                    t_val = float(parts[3])
                    distance[u_id][v_id] = d_val
                    travel_time[u_id][v_id] = t_val

        # Sort nodes by id (0 is depot)
        sorted_ids = sorted(raw_nodes.keys())
        for idx, cid in enumerate(sorted_ids):
            node_indices[cid] = idx
            nodes.append(raw_nodes[cid])

        return cls(
            name=name,
            nodes=nodes,
            distance=distance,
            travel_time=travel_time,
            max_vehicles=vehicles,
            capacity=capacity,
            dispatch_cost=dispatch_cost,
            unit_cost=unit_cost,
        )
