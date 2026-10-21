PORTNAME= dd-writer
PORTVERSION= 0.1.1
CATEGORIES= sysutils
MASTER_SITES= https://github.com/cleberalves40/DD-Writer/releases/download/v${PORTVERSION}/
DISTNAME= ${PORTNAME}-${PORTVERSION}

MAINTAINER= cleber@bsd.com.br
COMMENT= Qt utility for writing disk images to removable media
WWW= https://github.com/cleberalves40/DD-Writer

LICENSE= BSD3CLAUSE
LICENSE_FILE= ${WRKSRC}/LICENSE

RUN_DEPENDS= ${PYTHON_PKGNAMEPREFIX}qt5>0:devel/py-qt5 \
	${LOCALBASE}/bin/doas:security/doas

USES= desktop-file-utils python:run
SUB_FILES= dd-writer
SUB_LIST= DATADIR=${DATADIR} \
	PYTHON_CMD=${PYTHON_CMD}
NO_ARCH= yes
NO_BUILD= yes

PLIST_FILES= bin/dd-writer \
	share/applications/dd-writer.desktop \
	${DATADIR_REL}/DD-QT5.py \
	${DATADIR_REL}/dd_writer.py

do-install:
	${MKDIR} ${STAGEDIR}${DATADIR}
	${INSTALL_DATA} ${WRKSRC}/DD-QT5.py ${STAGEDIR}${DATADIR}/DD-QT5.py
	${INSTALL_DATA} ${WRKSRC}/dd_writer.py ${STAGEDIR}${DATADIR}/dd_writer.py
	${INSTALL_SCRIPT} ${WRKDIR}/dd-writer ${STAGEDIR}${PREFIX}/bin/dd-writer
	${INSTALL_DATA} ${FILESDIR}/dd-writer.desktop ${STAGEDIR}${PREFIX}/share/applications/dd-writer.desktop

.include <bsd.port.mk>