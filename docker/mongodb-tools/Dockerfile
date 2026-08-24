# ============================================================
# DOCKERFILE: MongoDB Database Tools Image (Version 100.18.0)
# ============================================================
# Contenedor dedicado para la ejecucion de respaldos (mongodump)
# y restauraciones (mongorestore) con herramientas aisladas y
# versionadas de forma explicita.
# ============================================================

FROM ubuntu:24.04

LABEL maintainer="Subdireccion Nacional de Arquitectura y Soluciones"
LABEL version="100.18.0"
LABEL description="Imagen cliente con MongoDB Database Tools 100.18.0 para respaldos HA"

ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias requeridas
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Descargar e instalar MongoDB Database Tools 100.18.0
ARG TOOLS_VERSION=100.18.0
RUN curl -fsSL "https://fastdl.mongodb.org/tools/db/mongodb-database-tools-ubuntu2404-x86_64-${TOOLS_VERSION}.tgz" -o /tmp/tools.tgz \
    && tar -xzf /tmp/tools.tgz -C /tmp \
    && cp /tmp/mongodb-database-tools-ubuntu2404-x86_64-${TOOLS_VERSION}/bin/* /usr/local/bin/ \
    && rm -rf /tmp/tools.tgz /tmp/mongodb-database-tools-*

# Crear directorio de trabajo /backup para punto de montaje
RUN mkdir -p /backup

WORKDIR /backup

# Comando por defecto: verificar version
CMD ["mongodump", "--version"]