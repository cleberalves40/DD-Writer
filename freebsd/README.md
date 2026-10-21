# FreeBSD Port

The port downloads its source archive from the public GitHub Release matching
`PORTVERSION`. For version `0.1.0`, it expects tag `v0.1.0` and asset
`dd-writer-0.1.0.tar.gz`.

## Build

With the FreeBSD Ports tree installed:

```sh
cd freebsd/dd-writer
make fetch
make package
```

Poudriere can fetch the same public release asset directly; no credentials or
pre-populated `DISTDIR` are needed.

To prepare a new release asset, archive the application sources from its tag:

```sh
git archive --format=tar --prefix=dd-writer-0.1.0/ v0.1.0   DD-QT5.py dd_writer.py LICENSE | gzip -n > dd-writer-0.1.0.tar.gz
```

Upload the archive to the GitHub Release for that tag. Update `PORTVERSION`,
`MASTER_SITES`, and `distinfo` together when releasing a new version.

The package depends on `devel/py-qt5`, `security/doas`, and the selected Python
runtime. Non-root writes use `doas -n`; the administrator must configure a
matching doas policy for `/bin/dd`. The application does not collect or store
passwords. The project is licensed under BSD 3-Clause.
