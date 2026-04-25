# Informe de Investigación: Servidor de Streaming con Nginx y RTMP

## 1. Introducción

Este documento presenta un análisis técnico del sistema de streaming desarrollado, el cual utiliza **Nginx** como servidor web y de streaming, configurado con el módulo **RTMP** (Real-Time Messaging Protocol) para manejar flujos de video en vivo.

---

## 2. ¿Qué es Nginx?

### 2.1 Definición

**Nginx** (se pronuncia "engine-x") es un servidor web de código abierto desarrollado por Igor Sysoev en 2004. Originalmente fue diseñado para resolver el problema C10K (manejar 10,000 conexiones simultáneas), lo que lo convierte en una solución altamente eficiente para servidores de alto rendimiento.

### 2.2 Características Principales

| Característica | Descripción |
|----------------|-------------|
| **Rendimiento** | Arquitectura orientada a eventos (event-driven), no bloqueante |
| **Uso de memoria** | Bajo consumo de recursos comparado con Apache |
| **Funcionalidad** | Servidor web, proxy reverso, balanceador de carga, cache |
| **Escalabilidad** | Maneja miles de conexiones simultáneas con poco uso de memoria |
| **Modularidad** | Sistema de módulos para extender funcionalidad |

### 2.3 Usos Comunes

- Servidor web estático
- Proxy reverso para aplicaciones
- Balanceador de carga
- Servidor de streaming (con módulos adicionales)
- Cache de contenido estático

---

## 3. Arquitectura del Proyecto

### 3.1 Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    docker-compose.yaml                      │
├──────────────────────────┬──────────────────────────────────┤
│     Servicio Nginx       │        Servicio FFmpeg          │
│  ┌────────────────────┐  │  ┌────────────────────────────┐  │
│  │ Servidor Web/HTTP  │  │  │ Encoder de Video           │  │
│  │ Servidor RTMP      │  │  │ (Captura y codificación)   │  │
│  │ Módulo HLS         │  │  │                             │  │
│  └────────────────────┘  │  └────────────────────────────┘  │
└──────────────────────────┴──────────────────────────────────┘
```

### 3.2 Flujo de Datos

```
Cámara/Fuente de Video
        │
        ▼
┌───────────────────┐
│   FFmpeg          │ ◄── Codifica y envía stream
│   (Productor)     │
└───────────────────┘
        │
        ▼ (Protocolo RTMP)
┌───────────────────┐
│   Nginx + RTMP    │ ◄── Servidor de streaming
│   (Servidor)      │
└───────────────────┘
        │
        ├──► Almacenamiento HLS (/tmp/hls)
        │
        ▼ (HTTP)
┌───────────────────┐
│   Cliente         │ ◄── Reproduce via HLS
│   (Consumidor)    │
└───────────────────┘
```

---

## 4. Análisis del Dockerfile

### 4.1 Estructura Multi-Stage

El Dockerfile utiliza una construcción de **múltiples etapas** (multi-stage build):

```dockerfile
FROM ${NGINX_FROM_IMAGE} AS builder  # Etapa 1: Constructor
# ... compilación de módulos ...

FROM ${NGINX_FROM_IMAGE}            # Etapa 2: Imagen final
# ... instalación de módulos ...
```

### 4.2 Etapa 1: Builder

**Propósito**: Compilar el módulo RTMP para nginx desde el código fuente.

**Pasos principales**:

1. **Verificación de parámetros**:
   ```dockerfile
   RUN if [ "$ENABLED_MODULES" = "" ]; then \
       echo "No additional modules enabled, exiting"; \
       exit 1; \
   fi
   ```
   - Verifica que se especifiquen los módulos a compilar
   - Si no hay módulos, aborta el build

2. **Instalación de dependencias**:
   ```dockerfile
   apt-get install -y patch make wget git devscripts debhelper dpkg-dev ...
   ```
   - Instala herramientas necesarias para compilar
   - build-essential: Compiladores y herramientas de build
   - git: Control de versiones para clonar repositorios
   - debhelper: Herramientas para crear paquetes Debian

3. **Verificación de seguridad (XSLScript)**:
   ```dockerfile
   XSLSCRIPT_SHA512="f7194c5198daeab9b3b0c3aebf006922c7df1d345d..."
   wget -O /tmp/xslscript.pl https://raw.githubusercontent.com/...
   if [ "$(cat /tmp/xslscript.pl | openssl sha512 -r)" = "$XSLSCRIPT_SHA512" ]; then
   ```
   - Descarga un script necesario para la compilación
   - Verifica su integridad mediante checksum SHA512
   - Previene la ejecución de código malicioso

4. **Clonación del repositorio pkg-oss**:
   ```dockerfile
   git clone -b ${NGINX_VERSION}-${PKG_RELEASE%%~*} https://github.com/nginx/pkg-oss/
   ```
   - Clona el repositorio oficial de nginx para construir módulos
   - Usa una versión específica basada en NGINX_VERSION

5. **Compilación de módulos**:
   ```dockerfile
   for module in $ENABLED_MODULES; do
       /pkg-oss/build_module.sh -v $NGINX_VERSION -f -y -o /tmp/packages -n $module ...
   done
   ```
   - Itera sobre cada módulo especificado en ENABLED_MODULES
   - Compila cada módulo usando el script oficial de nginx
   - Almacena los paquetes .deb resultantes en /tmp/packages

### 4.3 Etapa 2: Imagen Final

**Propósito**: Crear una imagen ligera con los módulos compilados.

```dockerfile
FROM ${NGINX_FROM_IMAGE}
RUN --mount=type=bind,target=/tmp/packages/,source=/tmp/packages/,from=builder \
    apt-get update \
    && . /tmp/packages/modules.env \
    && for module in $BUILT_MODULES; do
           apt-get install --no-install-suggests --no-install-recommends -y /tmp/packages/nginx-module-${module}_${NGINX_VERSION}*.deb;
       done
```

**Características**:
- Utiliza BuildKit mount para compartir archivos entre etapas
- Instala los paquetes .deb compilados en la etapa anterior
- No instala dependencias de build (reduce tamaño)
- Limpia caché de apt para minimizar tamaño final

---

## 5. Configuración de Nginx

### 5.1 nginx.conf (Configuración Principal)

```nginx
load_module /etc/nginx/modules/ngx_rtmp_module.so;

user root;
worker_processes auto;

error_log /var/log/nginx/error.log notice;
pid /var/run/nginx.pid;

events {
    worker_connections 1024;
}

include /etc/nginx/conf.d/rtmp.conf;
include /etc/nginx/conf.d/http.conf;
```

**Explicación de directivas**:

| Directiva | Descripción |
|-----------|-------------|
| `load_module` | Carga el módulo RTMP compilado dinámicamente |
| `user root` | Usuario que ejecuta los procesos de nginx |
| `worker_processes auto` | Número de procesos worker (auto = núcleos de CPU) |
| `error_log` | Ubicación del archivo de logs de errores |
| `worker_connections` | Máximo de conexiones por proceso worker |
| `include` | Incluye archivos de configuración adicionales |

### 5.2 rtmp.conf (Configuración RTMP)

```nginx
rtmp {
    server {
        listen ${RTMP_PORT};
        chunk_size 4096;
        allow publish all;
        
        application hls {
            live on;
            record off;
            
            hls on;
            hls_path /tmp/hls;
            hls_fragment 1;
        }
    }
}
```

**Análisis por directiva**:

#### Nivel servidor RTMP

| Directiva | Función |
|-----------|---------|
| `listen ${RTMP_PORT}` | Puerto donde escucha conexiones RTMP (default: 1935) |
| `chunk_size 4096` | Tamaño de cada chunk de datos (4KB) |
| `allow publish all` | Permite publicar desde cualquier origen |

#### Nivel aplicación (application hls)

| Directiva | Función |
|-----------|---------|
| `live on` | Habilita modo de streaming en vivo |
| `record off` | Desactiva grabación del stream |
| `hls on` | Activa HTTP Live Streaming |
| `hls_path /tmp/hls` | Directorio donde se guardan segmentos HLS |
| `hls_fragment 1` | Duración de cada fragmento en segundos |

### 5.3 http.conf (Configuración HTTP)

```nginx
http {
    server {
        listen ${HTTP_PORT};
        server_name ${NGINX_HOST};

        location / {
            root /usr/share/nginx/html;
            try_files $uri /index.html;
        }

        location /hls {
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            root /tmp;
        }
    }
}
```

**Análisis**:

#### Servidor HTTP

| Directiva | Descripción |
|-----------|-------------|
| `listen ${HTTP_PORT}` | Puerto HTTP (default: 80) |
| `server_name` | Nombre del servidor (desde variable de entorno) |

#### Location / (Página web estática)

| Directiva | Descripción |
|-----------|-------------|
| `root /usr/share/nginx/html` | Directorio raíz para archivos estáticos |
| `try_files $uri /index.html` | Busca archivo exacto, si no existe usa index.html |

#### Location /hls (Streaming HLS)

| Directiva | Descripción |
|-----------|-------------|
| `types` | Define tipos MIME para archivos HLS |
| `application/vnd.apple.mpegurl m3u8` | Archivo de lista de reproducción M3U8 |
| `video/mp2t ts` | Segmentos de video Transport Stream |
| `root /tmp` | Sirve archivos desde /tmp (donde nginx RTMP escribe HLS) |

---

## 6. Docker Compose

### 6.1 Servicio Nginx

```yaml
nginx:
    image: nginx-i
    build:
      context: nginx
      dockerfile: Dockerfile
      args:
        ENABLED_MODULES: rtmp
    env_file: .env
    ports:
      - "${HTTP_PORT}:${HTTP_PORT}"
      - "${RTMP_PORT}:${RTMP_PORT}"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/rtmp.conf:/etc/nginx/templates/rtmp.conf.template
      - ./nginx/http.conf:/etc/nginx/templates/http.conf.template
      - ./nginx/index.html:/usr/share/nginx/html/index.html
```

**Puertos expuestos**:
- **HTTP_PORT**: Para servir contenido web y HLS
- **RTMP_PORT**: Para recibir streams de FFmpeg

**Volúmenes montados**:
- `nginx.conf`: Configuración principal
- `rtmp.conf` y `http.conf`: Plantillas para Docker
- `index.html`: Página web estática

### 6.2 Servicio FFmpeg

```yaml
ffmpeg:
    image: ffmpeg-i
    build:
      context: ./ffmpeg
      dockerfile: Dockerfile
    depends_on:
      - nginx
```

**Propósito**: Producer de video que captura/entrena y envía stream al servidor Nginx.

---

## 7. Protocolo RTMP y HLS

### 7.1 RTMP (Real-Time Messaging Protocol)

- **Desarrollado por**: Macromedia/Adobe
- **Puerto default**: 1935
- **Uso**: Streaming en tiempo real de bajo latency
- **Transporte**: TCP con chunks variables

### 7.2 HLS (HTTP Live Streaming)

- **Desarrollado por**: Apple
- **Protocolo**: HTTP (sin puertos especiales)
- **Funcionamiento**:
  1. El servidor fragmenta el stream en chunks .ts
  2. Genera un archivo de lista .m3u8
  3. El cliente descarga la lista y los segmentos
- **Ventajas**: Funciona a través de firewalls y CDNs
- **Desventaja**: Mayor latencia que RTMP (~10-30 segundos)

---

## 8. Variables de Entorno (.env)

El sistema utiliza un archivo `.env` para configuración:

```
NGINX_HOST=nombre_del_contenedor
RTMP_PORT=1935
HTTP_PORT=80
FFMPEG_PATH=ffmpeg_encoder
```

---

## 9. Conclusiones

### 9.1 Resumen del Sistema

Este proyecto implementa un servidor de streaming completo utilizando:

1. **Nginx** como servidor base de alto rendimiento
2. **Módulo RTMP** para recibir streams en tiempo real
3. **Conversión a HLS** para compatibilidad con reproductores web
4. **Docker** para containerización y despliegue

### 9.2 Casos de Uso

- Streaming en vivo (live streaming)
- Transmisión de eventos
- Video bajo demanda (VOD) con grabación
- Servidor de replicación para redes de distribución (CDN)

### 9.3 Ventajas del Diseño

- **Escalabilidad**: Fácil de replicar con Docker Compose
- **Modularidad**: El Dockerfile permite agregar más módulos
- **Compatibilidad**: HLS funciona en todos los navegadores y móviles
- **Simplicidad**: Configuración clara y separada

---

## 10. Referencias

- [Nginx Official Documentation](https://nginx.org/en/docs/)
- [nginx-rtmp-module](https://github.com/arut/nginx-rtmp-module)
- [Docker Multi-stage Builds](https://docs.docker.com/develop/develop-images/multistage-build/)
- [HLS Specification](https://datatracker.ietf.org/doc/html/rfc8216)

---

*Informe generado el 25 de abril de 2026*