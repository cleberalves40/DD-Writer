import os
import plistlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Device:
    path: str
    size_bytes: int
    description: str


def _parse_freebsd_disks(output):
    disks = []
    name = None
    size = None
    description = ""

    def add_disk():
        if name and size:
            disks.append(Device(f"/dev/{name}", size, description or name))

    for line in output.splitlines():
        if line.startswith("Geom name:"):
            add_disk()
            name = line.split(":", 1)[1].strip()
            size = None
            description = ""
        elif name and line.strip().startswith("Mediasize:"):
            match = re.search(r"Mediasize:\s*(\d+)", line)
            if match:
                size = int(match.group(1))
        elif name and line.strip().startswith("descr:"):
            description = line.split(":", 1)[1].strip()

    add_disk()
    return disks


def _freebsd_mounted_disk_names():
    result = subprocess.run(
        ["mount", "-p"], check=True, capture_output=True, text=True
    )
    mounted_names = set()
    mounted_providers = set()
    for line in result.stdout.splitlines():
        source = line.split(maxsplit=1)[0] if line.split() else ""
        if source.startswith("/dev/"):
            mounted_providers.add(source.removeprefix("/dev/"))
            mounted_names.add(os.path.basename(os.path.realpath(source)))
    labels = subprocess.run(
        ["glabel", "status"], capture_output=True, text=True, check=False
    )
    label_consumers = _freebsd_label_consumers(labels.stdout)
    for provider in mounted_providers:
        if provider in label_consumers:
            mounted_names.add(label_consumers[provider])
    if shutil.which("zpool"):
        pools = subprocess.run(
            ["zpool", "status", "-P"], capture_output=True, text=True, check=False
        )
        mounted_names.update(_freebsd_zpool_disk_names(pools.stdout))
    return mounted_names


def _freebsd_label_consumers(output):
    consumers = {}
    for line in output.splitlines():
        fields = line.split()
        if len(fields) >= 3 and fields[0] != "Name":
            consumers[fields[0]] = os.path.basename(fields[-1])
    return consumers


def _freebsd_zpool_disk_names(output):
    disk_names = set()
    for provider in re.findall(r"/dev/[^\s]+", output):
        name = os.path.basename(os.path.realpath(provider))
        parent = re.sub(r"(?:p\d+|s\d+[a-z]?|[a-z])$", "", name)
        disk_names.add(parent or name)
    return disk_names


def _is_mounted_disk(name, mounted_names):
    partition_suffix = re.compile(r"(?:p\d+|s\d+[a-z]?|[a-z])$")
    for mounted_name in mounted_names:
        if mounted_name == name:
            return True
        if mounted_name.startswith(name) and partition_suffix.fullmatch(
            mounted_name[len(name):]
        ):
            return True
    return False


def _list_freebsd_devices():
    result = subprocess.run(
        ["geom", "disk", "list"], check=True, capture_output=True, text=True
    )
    mounted_names = _freebsd_mounted_disk_names()
    return [
        device
        for device in _parse_freebsd_disks(result.stdout)
        if not _is_mounted_disk(Path(device.path).name, mounted_names)
    ]


def _list_macos_devices():
    result = subprocess.run(
        ["/usr/sbin/diskutil", "list", "-plist", "external", "physical"],
        check=True,
        capture_output=True,
    )
    disk_list = plistlib.loads(result.stdout)
    disks_by_id = {
        disk.get("DeviceIdentifier"): disk
        for disk in disk_list.get("AllDisksAndPartitions", [])
        if disk.get("DeviceIdentifier")
    }
    devices = []
    for identifier in disk_list.get("WholeDisks", []):
        disk = disks_by_id.get(identifier, {})
        if any(partition.get("MountPoint") for partition in disk.get("Partitions", [])):
            continue
        info_result = subprocess.run(
            ["/usr/sbin/diskutil", "info", "-plist", f"/dev/{identifier}"],
            check=True,
            capture_output=True,
        )
        info = plistlib.loads(info_result.stdout)
        size = info.get("TotalSize")
        if size:
            raw_path = f"/dev/r{identifier}"
            devices.append(
                Device(raw_path, int(size), info.get("MediaName", identifier))
            )
    return devices


def list_devices():
    try:
        if sys.platform.startswith("freebsd"):
            return _list_freebsd_devices()
        if sys.platform == "darwin":
            return _list_macos_devices()
        raise OSError(f"Unsupported operating system: {sys.platform}")
    except subprocess.CalledProcessError as error:
        detail = error.stderr.strip() if error.stderr else str(error)
        raise OSError(f"Disk discovery failed: {detail}") from error


def validate_write(image_path, device_path, devices=None):
    image = Path(image_path)
    try:
        image_stat = image.stat()
    except OSError as error:
        raise ValueError(f"Cannot read image: {error}") from error
    if not image.is_file() or image_stat.st_size == 0:
        raise ValueError("The image must be a non-empty regular file.")

    available_devices = list_devices() if devices is None else devices
    device = next((item for item in available_devices if item.path == device_path), None)
    if device is None:
        raise ValueError("The selected device is no longer available.")
    if image_stat.st_size > device.size_bytes:
        raise ValueError("The image is larger than the selected device.")
    return image_stat.st_size, device


def build_dd_command(image_path, device_path):
    command = ["/bin/dd", f"if={image_path}", f"of={device_path}", "bs=1m", "status=progress"]
    if os.geteuid() == 0:
        return command
    if sys.platform.startswith("freebsd"):
        doas = shutil.which("doas")
        if not doas:
            raise RuntimeError("doas is required to authorize disk writes on FreeBSD.")
        return [doas, "-n", *command]
    if sys.platform == "darwin":
        return ["/usr/bin/sudo", "-n", *command]
    raise RuntimeError("No supported privilege authorization method is available.")


def write_image(image_path, device_path, process_factory=subprocess.Popen):
    image_size, _ = validate_write(image_path, device_path)
    command = build_dd_command(image_path, device_path)
    process = process_factory(
        command,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=sys.platform == "darwin",
    )
    return process, image_size