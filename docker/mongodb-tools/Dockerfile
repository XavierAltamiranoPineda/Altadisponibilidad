# ============================================================
# DOCKERFILE: MongoDB Database Tools Image
# ============================================================

ARG BASE_IMAGE=ubuntu:26.04
FROM ${BASE_IMAGE}

ARG TOOLS_VERSION=100.18.0

LABEL maintainer="Subdireccion Nacional de Arquitectura y Soluciones"
LABEL version="${TOOLS_VERSION}"
LABEL description="Imagen cliente con MongoDB Database Tools para respaldos HA"

# Dependencias runtime requeridas por mongodump y mongorestore
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libgssapi-krb5-2 \
    && rm -rf /var/lib/apt/lists/*

# Copiar binarios versionados desde el proyecto
COPY tools/mongodb-database-tools/${TOOLS_VERSION}/bin/mongodump \
     /usr/local/bin/mongodump

COPY tools/mongodb-database-tools/${TOOLS_VERSION}/bin/mongorestore \
     /usr/local/bin/mongorestore

RUN chmod 0755 \
      /usr/local/bin/mongodump \
      /usr/local/bin/mongorestore \
    && mkdir -p /backup

WORKDIR /backup

CMD ["mongodump", "--version"]