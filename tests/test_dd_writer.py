import tempfile
import unittest
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

from dd_writer import (
    Device,
    _freebsd_label_consumers,
    _freebsd_zpool_disk_names,
    _is_mounted_disk,
    _parse_freebsd_disks,
    build_dd_command,
    estimate_remaining_seconds,
    list_devices,
    validate_write,
    write_image,
)


class FreeBSDDiskParsingTests(unittest.TestCase):
    def test_parses_disk_size_and_description(self):
        output = """Geom name: ada0
Providers:
1. Name: ada0
   Mediasize: 960197124096 (894G)
   Sectorsize: 512
   descr: KINGSTON SA400S37960G
"""
        self.assertEqual(
            _parse_freebsd_disks(output),
            [Device("/dev/ada0", 960197124096, "KINGSTON SA400S37960G")],
        )

    def test_excludes_mounted_partitions_and_root_disk(self):
        mounted_names = {"ada0p2", "da0s1a"}
        self.assertTrue(_is_mounted_disk("ada0", mounted_names))
        self.assertTrue(_is_mounted_disk("da0", mounted_names))
        self.assertFalse(_is_mounted_disk("da1", mounted_names))

    def test_maps_zfs_pool_partition_to_whole_disk(self):
        names = _freebsd_zpool_disk_names("  /dev/ada0p3  ONLINE  0 0 0\n")
        self.assertEqual(names, {"ada0"})

    def test_maps_mounted_gpt_label_to_physical_partition(self):
        output = "Name Status Components\ngpt/efiboot0 N/A da0p1\n"
        consumers = _freebsd_label_consumers(output)
        self.assertEqual(consumers["gpt/efiboot0"], "da0p1")
        self.assertTrue(_is_mounted_disk("da0", set(consumers.values())))


class WriteValidationTests(unittest.TestCase):
    def test_accepts_image_that_fits_selected_device(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.img"
            image.write_bytes(b"image")
            size, device = validate_write(
                image, "/dev/da1", [Device("/dev/da1", 10, "USB")]
            )
        self.assertEqual(size, 5)
        self.assertEqual(device.path, "/dev/da1")

    def test_rejects_image_larger_than_device(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.img"
            image.write_bytes(b"too large")
            with self.assertRaisesRegex(ValueError, "larger than"):
                validate_write(image, "/dev/da1", [Device("/dev/da1", 2, "USB")])

    def test_rejects_device_not_in_current_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / "image.img"
            image.write_bytes(b"image")
            with self.assertRaisesRegex(ValueError, "no longer available"):
                validate_write(image, "/dev/ada0", [Device("/dev/da1", 10, "USB")])


class EtaEstimateTests(unittest.TestCase):
    def test_estimates_remaining_time_from_raw_byte_rate(self):
        self.assertEqual(estimate_remaining_seconds(1000, 200, 10), 40)

    def test_returns_zero_when_all_bytes_are_transferred(self):
        self.assertEqual(estimate_remaining_seconds(1000, 1000, 10), 0)

    def test_rejects_unavailable_rate_inputs(self):
        self.assertIsNone(estimate_remaining_seconds(1000, 0, 10))
        self.assertIsNone(estimate_remaining_seconds(1000, 100, 0))


class WriteCommandTests(unittest.TestCase):
    def test_uses_doas_and_argument_list_on_freebsd(self):
        with (
            patch("dd_writer.os.geteuid", return_value=1000),
            patch("dd_writer.sys.platform", "freebsd15"),
            patch("dd_writer.shutil.which", return_value="/usr/local/bin/doas"),
        ):
            command = build_dd_command("/tmp/image with spaces.img", "/dev/da1")
        self.assertEqual(
            command,
            [
                "/usr/local/bin/doas",
                "-n",
                "/bin/dd",
                "if=/tmp/image with spaces.img",
                "of=/dev/da1",
                "bs=1m",
                "status=progress",
            ],
        )

    def test_wraps_disk_discovery_command_errors(self):
        failure = subprocess.CalledProcessError(1, "geom", stderr="permission denied")
        with (
            patch("dd_writer.sys.platform", "freebsd15"),
            patch("dd_writer._list_freebsd_devices", side_effect=failure),
        ):
            with self.assertRaisesRegex(OSError, "permission denied"):
                list_devices()

    def test_preserves_freebsd_control_terminal_for_doas(self):
        process_factory = Mock()
        device = Device("/dev/da1", 10, "USB")
        with (
            patch("dd_writer.sys.platform", "freebsd15"),
            patch("dd_writer.os.geteuid", return_value=1001),
            patch("dd_writer.shutil.which", return_value="/usr/local/bin/doas"),
            patch("dd_writer.validate_write", return_value=(5, device)),
        ):
            write_image("/tmp/image.img", "/dev/da1", process_factory=process_factory)
        self.assertFalse(process_factory.call_args.kwargs["start_new_session"])


if __name__ == "__main__":
    unittest.main()