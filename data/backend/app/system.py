import os
import psutil


def get_battery_info():
    battery = psutil.sensors_battery()

    if battery is None:
        return {
            "Battery": "Unknown",
            "Charging": "Unknown"
        }

    return {
        "Battery": f"{int(battery.percent)}%",
        "Charging": "Yes" if battery.power_plugged else "No"
    }


def get_cpu_info():
    return {
        "CPU Usage": f"{psutil.cpu_percent(interval=1)}%"
    }


def get_ram_info():
    memory_info = psutil.virtual_memory()
    return {
        "RAM Usage": f"{memory_info.percent}%"
    }


def get_disk_info():
    disk_path = os.path.abspath(os.sep)
    disk_info = psutil.disk_usage(disk_path)
    return {
        "Disk Usage": f"{disk_info.percent}%"
    }


def get_system_info():
    system_info = {}
    system_info.update(get_battery_info())
    system_info.update(get_cpu_info())
    system_info.update(get_ram_info())
    system_info.update(get_disk_info())
    return system_info

    