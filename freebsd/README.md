# Internal FreeBSD Port

This port fetches its distfile from the GitHub Release matching `PORTVERSION`.
The asset name must be `dd-writer-${PORTVERSION}.tar.gz` on the tag
`v${PORTVERSION}`. Do not add GitHub credentials to the port.

## Build

Keep `PORTVERSION` synchronized with a reviewed release tag. Build the asset
from the exact source files in that tag, then attach it to a GitHub Release:

```sh
git archive --format=tar --prefix=dd-writer-0.1.0/ v0.1.0 \
  DD-QT5.py dd_writer.py LICENSE | gzip -n > dd-writer-0.1.0.tar.gz
```

Create the GitHub Release with tag `v0.1.0` and upload `dd-writer-0.1.0.tar.gz`
as a release asset. Then verify its checksum and build the port:

```sh
cd freebsd/dd-writer
make makesum
make fetch
make package
```

The repository and its releases are currently private. GitHub release assets
from a private repository are not anonymously fetchable, so internal Poudriere
builds must pre-populate `DISTDIR` or use an authenticated internal mirror.
Public Ports builds require the release asset to be anonymously accessible.

The package depends on `devel/py-qt5`, `security/doas`, and the selected Python
runtime. Non-root writes use `doas -n`; the administrator must configure a
matching doas policy for `/bin/dd`. The application does not collect or store
passwords.

## Release Gate

The project uses the BSD 3-Clause License. Keep this port private until a
reviewed release tag exists and the package has passed an install test and a
write test against disposable media. Public Ports submission also requires an
anonymously fetchable source archive.