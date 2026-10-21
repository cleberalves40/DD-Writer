# Internal FreeBSD Port

This port is intended for private builds. The repository is private, so build
hosts must receive the distfile through the organization's private artifact
cache. Do not add GitHub credentials to the port or publish the distfile.

## Build

Keep `PORTVERSION` in `dd-writer/Makefile` synchronized with a reviewed source
tag. On an authorized build host, create the archive from that tag and place it
in the configured ports distfile cache:

```sh
git archive --format=tar --prefix=dd-writer-0.1.0/ v0.1.0 | gzip -n \
  > /usr/ports/distfiles/dd-writer-0.1.0.tar.gz
cd freebsd/dd-writer
make makesum
make package
```

For Poudriere, publish that archive only to the private distfile cache used by
the build jail. `MASTER_SITES= LOCAL/cleberalves40` keeps normal source URLs out
of the port; the cached distfile is used by the build framework.

The package depends on `devel/py-qt5`, `security/doas`, and the selected Python
runtime. Non-root writes use `doas -n`; the administrator must configure a
matching doas policy for `/bin/dd`. The application does not collect or store
passwords.

## Release Gate

The project uses the BSD 3-Clause License. Keep this port private until a
reviewed release tag exists and the package has passed an install test and a
write test against disposable media. Public Ports submission also requires an
anonymously fetchable source archive.