from kubernetes import client, config

# For now, exception handler will be here and only printing
def _handle_exception(ex):
        print('---------------------------------------')
        print('Exception:')
        print('---------------------------------------')
        print(ex)
        print('---------------------------------------')


# ---------- Parsers ----------
def _parse_cpu(value: str) -> float:
    if value.endswith("m"):
        return int(value[:-1]) / 1000
    if value.endswith("n"):
        return int(value[:-1]) / 1_000_000_000
    return float(value)

def _parse_memory(value: str) -> float:
    """
    Convert memory string to GiB.
    Handles:
        - Binary units: Ki, Mi, Gi, Ti
        - SI units: K, M, G, T
        - Plain integers (bytes)
    Returns: float GiB
    """
    value = value.strip()
    try:
        if value.endswith("Ki"):
            return int(value[:-2]) / 1024 / 1024
        elif value.endswith("Mi"):
            return int(value[:-2]) / 1024
        elif value.endswith("Gi"):
            return int(value[:-2])
        elif value.endswith("Ti"):
            return int(value[:-2]) * 1024
        elif value.endswith("K"):
            return int(value[:-1]) / 1024 / 1024
        elif value.endswith("M"):
            return int(value[:-1]) / 1024
        elif value.endswith("G"):
            return int(value[:-1])
        elif value.endswith("T"):
            return int(value[:-1]) * 1024
        else:
            return int(value) / 1024 / 1024 / 1024
    except ValueError as ex:
        _handle_exception(f"Unable to parse memory value '{value}': {ex}")
        return 0

# ---------- Core client ----------
def _get_k8s_client():
    try:
        config.load_incluster_config()
    except:
        config.load_kube_config()
    return client.CoreV1Api(), client.CustomObjectsApi()

# ---------- Pod metrics ----------
def _get_pod_counts(v1: client.CoreV1Api):
    pods_status = {"running": 0, "pending": 0, "failed": 0}
    for pod in v1.list_pod_for_all_namespaces().items:
        phase = pod.status.phase.lower()
        if phase in pods_status:
            pods_status[phase] += 1
    total_pods = sum(pods_status.values())
    return pods_status, total_pods

# ---------- Node metrics ----------
def _get_nodes(v1: client.CoreV1Api, custom: client.CustomObjectsApi):
    nodes_info = []
    nodes = v1.list_node()
    for node in nodes.items:
        cap = node.status.capacity
        alloc = node.status.allocatable
        nodes_info.append({
            "name": node.metadata.name,
            "cpu_capacity": int(cap.get("cpu", 0)),
            "cpu_allocatable": int(alloc.get("cpu", 0)),
            "mem_capacity": round(int(cap.get("memory", "0Ki")[:-2]) / 1024 / 1024, 2),  # GiB
            "mem_allocatable": round(int(alloc.get("memory", "0Ki")[:-2]) / 1024 / 1024, 2),  # GiB
            "ready": any(
                cond.type == "Ready" and cond.status == "True"
                for cond in node.status.conditions
            ),
        })

    # Merge usage from metrics server
    try:
        usage = custom.list_cluster_custom_object(
            group="metrics.k8s.io", version="v1beta1", plural="nodes"
        )
        usage_map = {}
        for u in usage["items"]:
            name = u["metadata"]["name"]
            cpu_usage = _parse_cpu(u["usage"]["cpu"])
            mem_usage = _parse_memory(u["usage"]["memory"])
            usage_map[name] = {"cpu_usage": cpu_usage, "mem_usage": mem_usage}

        total_cpu_usage = total_mem_usage = total_cpu_capacity = total_mem_capacity = 0
        for node in nodes_info:
            u = usage_map.get(node["name"], {})
            node["cpu_usage"] = u.get("cpu_usage", 0)
            node["mem_usage"] = round(u.get("mem_usage", 0), 2)
            node["cpu_percent"] = (
                round((node["cpu_usage"] / node["cpu_capacity"]) * 100, 1)
                if node["cpu_capacity"] > 0 else None
            )
            node["mem_percent"] = (
                round((node["mem_usage"] / node["mem_allocatable"]) * 100, 1)
                if node["mem_allocatable"] > 0 else None
            )

            total_cpu_usage += node["cpu_usage"]
            total_mem_usage += node["mem_usage"]
            total_cpu_capacity += node["cpu_capacity"]
            total_mem_capacity += node["mem_allocatable"]

        cluster_cpu_percent = round((total_cpu_usage / total_cpu_capacity) * 100, 1) if total_cpu_capacity else None
        cluster_mem_percent = round((total_mem_usage / total_mem_capacity) * 100, 1) if total_mem_capacity else None

    except Exception as ex:
        _handle_exception(ex)
        for node in nodes_info:
            node["cpu_usage"] = node["mem_usage"] = None
            node["cpu_percent"] = node["mem_percent"] = None
        cluster_cpu_percent = cluster_mem_percent = None

    return nodes_info, cluster_cpu_percent, cluster_mem_percent



def _collect_k8s_pod_details():
    v1, custom = _get_k8s_client()
    pod_details = []

    # Get metrics for current usage (requires metrics-server)
    pod_usage_map = {}
    try:
        usage = custom.list_cluster_custom_object(
            group="metrics.k8s.io", version="v1beta1", plural="pods"
        )
        for item in usage["items"]:
            ns = item["metadata"]["namespace"]
            name = item["metadata"]["name"]
            container_usages = {}
            for c in item["containers"]:
                cpu = _parse_cpu(c["usage"]["cpu"])
                mem = _parse_memory(c["usage"]["memory"])
                container_usages[c["name"]] = {"cpu": cpu, "mem": mem}
            pod_usage_map[(ns, name)] = container_usages
    except Exception as ex:
        _handle_exception(ex)

    # Iterate all pods
    for pod in v1.list_pod_for_all_namespaces().items:
        ns = pod.metadata.namespace
        pod_name = pod.metadata.name
        node_name = pod.spec.node_name
        status = pod.status.phase
        restarts = sum(c.restart_count for c in pod.status.container_statuses or [])

        cpu_req_total = cpu_lim_total = 0.0
        mem_req_total = mem_lim_total = 0.0
        missing_resources = False

        for container in pod.spec.containers:
            req = container.resources.requests or {}
            lim = container.resources.limits or {}

            cpu_req = _parse_cpu(req.get("cpu", "0")) if req.get("cpu") else None
            cpu_lim = _parse_cpu(lim.get("cpu", "0")) if lim.get("cpu") else None
            mem_req = _parse_memory(req.get("memory", "0")) if req.get("memory") else None
            mem_lim = _parse_memory(lim.get("memory", "0")) if lim.get("memory") else None

            if cpu_req is None and cpu_lim is None and mem_req is None and mem_lim is None:
                missing_resources = True

            cpu_req_total += cpu_req or 0
            cpu_lim_total += cpu_lim or 0
            mem_req_total += mem_req or 0
            mem_lim_total += mem_lim or 0

        # Get current usage from metrics server if available
        usage = pod_usage_map.get((ns, pod_name), {})
        cpu_usage_total = sum(u.get("cpu", 0) for u in usage.values())
        mem_usage_total = sum(u.get("mem", 0) for u in usage.values())

        pod_details.append({
            "namespace": ns,
            "name": pod_name,
            "node": node_name,
            "status": status,
            "restarts": restarts,
            "cpu_request": round(cpu_req_total, 2) if cpu_req_total else None,
            "cpu_limit": round(cpu_lim_total, 2) if cpu_lim_total else None,
            "mem_request": round(mem_req_total, 2) if mem_req_total else None,
            "mem_limit": round(mem_lim_total, 2) if mem_lim_total else None,
            "cpu_usage": round(cpu_usage_total, 2) if cpu_usage_total else None,
            "mem_usage": round(mem_usage_total, 2) if mem_usage_total else None,
            "missing_resources": missing_resources,
        })

    return pod_details


# ---------- Wrappers ----------
def collect_k8s_metrics_summary():
    v1, custom = _get_k8s_client()
    pods_status, total_pods = _get_pod_counts(v1)
    nodes_info, cluster_cpu_percent, cluster_mem_percent = _get_nodes(v1, custom)
    return pods_status, nodes_info, total_pods, cluster_cpu_percent, cluster_mem_percent

def collect_k8s_metrics_detailed():
    """
    Returns the same summary as the high-level dashboard,
    plus pod-level details.
    """
    pods_status, nodes_info, total_pods, cluster_cpu_percent, cluster_mem_percent = collect_k8s_metrics_summary()
    pod_details = _collect_k8s_pod_details()

    # ---------- Alerts ----------
    cluster_alerts = []
    if pods_status["pending"] > 0:
        cluster_alerts.append(f"{pods_status['pending']} pods pending")
    if pods_status["failed"] > 0:
        cluster_alerts.append(f"{pods_status['failed']} pods failed")

    return {
        "pods_status": pods_status,
        "total_pods": total_pods,
        "nodes_info": nodes_info,
        "cluster_cpu_percent": cluster_cpu_percent,
        "cluster_mem_percent": cluster_mem_percent,
        "pod_details": pod_details,
        "cluster_alerts": cluster_alerts,
    }
