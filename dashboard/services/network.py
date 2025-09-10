import requests
import subprocess
import re

mac_to_name = {
    "8:b4:b1:23:fa:df": "Google Nest Wifi Router",
    "24:d7:eb:9d:7a:0": "Living Room TV",
    "c8:4a:a0:d8:7a:66": "John’s iPhone",
    # Add more mappings as needed
}


# Configuration
router_ip = "192.168.86.1"


def _status_endpoint() -> dict:

    try:
        response = requests.get(f"http://{router_ip}/api/v1/status", timeout=5)
        response.raise_for_status()
        json_response = response.json()

        uptime_seconds = json_response["system"]["uptime"]
        uptime_days, remainder = divmod(uptime_seconds, 86400)
        uptime_hours, remainder = divmod(remainder, 3600)
        uptime_minutes, _ = divmod(remainder, 60)

        lease_seconds = json_response['wan']['leaseDurationSeconds']
        lease_days, remainder = divmod(uptime_seconds, 86400)
        lease_hours, remainder = divmod(remainder, 3600)
        lease_minutes, _ = divmod(remainder, 60)

        status = {
            "uptime_days": uptime_days,
            "uptime_hours": uptime_hours,
            "uptime_minutes": uptime_minutes,
            "led_status": json_response["system"]["ledAnimation"],
            "online": json_response["wan"]["online"],
            "ip_method": json_response["wan"]["ipMethod"].upper(),
            "ip_address": json_response["wan"]["localIpAddress"],
            "gateway": json_response["wan"]["gatewayIpAddress"],
            "local_ip_address": json_response["wan"]["localIpAddress"],
            "lease_days": lease_days,
            "lease_hours": lease_hours,
            "lease_minutes": lease_minutes,
            "dns_servers": ", ".join(json_response["wan"]["nameServers"]),
            "ethernet_link": json_response["wan"]["ethernetLink"],
            "update_required": json_response["software"]["updateRequired"]
        }
    except requests.exceptions.HTTPError as ex:
        status = {
            "Error": ex
        }
    except requests.exceptions.RequestException as ex:
        status = {
            "Error": ex
        }

    return status

def _get_arp_table():
    try:
        result = subprocess.run(['arp', '-a'], capture_output=True, text=True)
        arp_table = {}
        for line in result.stdout.splitlines():
            match = re.search(r'\(([\d.]+)\)\s+at\s+([0-9a-f:]+)', line)
            if match:
                ip, mac = match.groups()
                arp_table[ip] = mac
        return arp_table
    except Exception as e:
        print(f"Error retrieving ARP table: {str(e)}")
        return {}

def collect_network_details():
    status = _status_endpoint()
    arp_table = _get_arp_table()
    status['devices'] = len(arp_table)
    status['details'] = []
    for ip, mac in arp_table.items():
        if mac in mac_to_name:
            name = mac_to_name[mac]
        else:
            name = 'Unknown'
        status['details'].append({
            'ip': ip,
            'mac': mac,
            'name': name
        })
    return status

def collect_network_summary():
    status = _status_endpoint()
    arp_table = _get_arp_table()
    status['devices'] = len(arp_table)
    return status

