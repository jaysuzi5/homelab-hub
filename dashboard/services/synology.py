# dashboard/services/synology.py
import os
from dotenv import load_dotenv
from synology_dsm import SynologyDSM

load_dotenv()

NAS_IP = "192.168.86.210"
NAS_PORT = 5000
NAS_USER = "jay"
NAS_PASSWORD = os.getenv("SYNOLOGY_PASSWORD")


def _get_metrics():
    """
    Connect to the Synology NAS and return a structured dictionary with
    system info, CPU/memory usage, network stats, and storage info.
    """
    try:
        api = SynologyDSM(NAS_IP, NAS_PORT, NAS_USER, NAS_PASSWORD, use_https=False)

        # Update all info
        api.information.update()
        api.utilisation.update()
        api.storage.update()

        # System info
        uptime_seconds = api.information.uptime
        days, remainder = divmod(uptime_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        system_info = {
            "model": api.information.model,
            "ram_mb": api.information.ram,
            "serial": api.information.serial,
            "temperature": api.information.temperature,
            "temperature_warn": api.information.temperature_warn,
            "uptime_days": days,
            "uptime_hours": hours,
            "uptime_minutes": minutes,
            "dsm_version": api.information.version_string,
        }

        # Utilization
        utilization = {
            "cpu_percent": api.utilisation.cpu_total_load,
            "memory_percent": api.utilisation.memory_real_usage,
            "net_up": api.utilisation.network_up(),
            "net_down": api.utilisation.network_down(),
        }

        # Storage volumes
        # print(api.storage._data)
        volumes = []
        overall_bytes = 0
        overall_used_bytes = 0
        for vol_id in api.storage.volumes_ids:
            total_bytes = api.storage.volume_size_total(vol_id)
            used_bytes = api.storage.volume_size_used(vol_id)
            if total_bytes:
                overall_bytes += total_bytes
            if used_bytes:
                overall_used_bytes += used_bytes    
            if vol_id == "volume_1":
                vol_name = "nas"
            elif vol_id == "volume_2":
                vol_name = "k8s-data"
            volumes.append({
                "name": vol_name,
                "id": vol_id,
                "status": api.storage.volume_status(vol_id),
                "percent_used": api.storage.volume_percentage_used(vol_id),
                "size_total": round(total_bytes / (1024**4), 2) if total_bytes else None,
                "size_used": round(used_bytes / (1024**4), 2) if used_bytes else None,                
            })

        utilization["overall_percent_used"] = int(round((overall_used_bytes/overall_bytes)*100,0)) if overall_bytes > 0 else 0

        # Disks
        disks = []
        for disk_id in api.storage.disks_ids:
            disks.append({
                "id": disk_id,
                "name": api.storage.disk_name(disk_id),
                "status": api.storage.disk_status(disk_id),
                "smart_status": api.storage.disk_smart_status(disk_id),
                "temperature": api.storage.disk_temp(disk_id),
            })

        return {
            "system": system_info,
            "utilization": utilization,
            "volumes": volumes,
            "disks": disks,
        }

    except Exception as ex:
        return {"error": str(ex)}


# ---------- Wrappers ----------
def collect_synology_metrics_summary():
    return _get_metrics()        