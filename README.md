# DD Image Writer

DD Image Writer is a small PyQt5 application for writing image files to
removable disks. It currently has disk discovery backends for macOS and
FreeBSD.

## Run

Install Python 3 and PyQt5, then launch the application:

```sh
python3 DD-QT5.py
```

On FreeBSD, the internal port in `freebsd/dd-writer` declares the runtime
dependencies. Non-root writes use `doas -n`; the local doas policy must
authorize `/bin/dd` for the user or group running the app. The app does not
collect or store passwords. On macOS, writes require an existing sudo
authorization.

The application hides mounted disks and disks backing active FreeBSD ZFS pools,
checks that the image fits the selected device, and asks for confirmation
before erasing it. Writing an image permanently destroys data on the selected
device; only use removable media whose contents can be erased.

## Tests

Run the safe, hardware-independent tests with:

```sh
python3 -m unittest discover -s tests -v
```

## FreeBSD Port

See [`freebsd/README.md`](freebsd/README.md) for the private distfile workflow
and release gates. The project is licensed under the BSD 3-Clause License;
public Ports submission still requires an anonymously fetchable source archive.