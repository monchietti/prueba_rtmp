# Informe de Arquitectura - Sistema de Streaming en Vivo

## 1. Visión General del Sistema

Este proyecto implementa un servidor de streaming en vivo utilizando Nginx con el módulo RTMP, combinado con un frontend Angular para la reproducción del stream y un script Python para procesamiento adicional.

```
┌─────────────┐     RTMP      ┌─────────────┐    HLS     ┌─────────────┐
│  OBS/Fuente │ ─────────────▶│    Nginx    │ ──────────▶│  Reproduc.  │
│  de Video   │               │  + RTMP     │            │  Angular    │
└─────────────┘               │  + HLS       │            └─────────────┘
                              └─────────────┘
                                     │
                                     ▼
                              ┌─────────────┐
                              │   Python    │
                              │   Script    │
                              └─────────────┘
```

---

## 2. Arquitectura de Nginx con Módulo RTMP

### 2.1 Componentes Principales

| Componente | Descripción |
|------------|-------------|
| **Nginx** | Servidor web/base |
| **ngx_rtmp_module** | Módulo que añade soporte para protocolo RTMP |
| **HLS (HTTP Live Streaming)** | Protocolo de streaming adaptativo |

### 2.2 Configuración Base de Nginx

Ubicación: [nginx/nginx.conf](nginx/nginx.conf)

```nginx
load_module /etc/nginx/modules/ngx_rtmp_module.so;

user root;
worker_processes auto;

error_log /var/log/nginx/error.log notice;
pid /var/run/nginx.pid;

events {
    worker_connections 1024; # Número máximo de conexiones simultáneas
}

include /etc/nginx/conf.d/rtmp.conf; # Incluir configuración RTMP
include /etc/nginx/conf.d/http.conf; # Incluir configuración HTTP
```

#### Explicación de Directivas:

| Directiva | Descripción |
|-----------|-------------|
| **`load_module`** | Carga dinámicamente el módulo RTMP en tiempo de ejecución |
| **`user root`** | Usuario que ejecuta los worker processes |
| **`worker_processes auto`** | Nginx crea automáticamente tantos procesos worker como núcleos de CPU tenga el sistema |
| **`error_log`** | Define la ubicación y nivel de detalle para los logs de errores |
| **`pid`** | Archivo que almacena el ID del proceso maestro de Nginx |
| **`worker_connections`** | Número máximo de conexiones simultáneas por cada worker (1024 = hasta 1024 clientes por worker) |
| **`include`** | Inserta el contenido de otros archivos de configuración (rtmp.conf y http.conf) |

#### Funcionamiento del Include:

```
nginx.conf
    │
    ├── load_module ngx_rtmp_module.so  ← Carga el módulo RTMP
    │
    ├── include /etc/nginx/conf.d/rtmp.conf   ← Configuración RTMP (puerto 1935)
    │
    └── include /etc/nginx/conf.d/http.conf   ← Configuración HTTP (puerto 5555)
```

> **Nota**: El orden es importante. Primero se carga el módulo RTMP, luego se incluyen las configuraciones que lo utilizan.

### 2.3 Configuración RTMP

Ubicación: [nginx/rtmp.conf](nginx/rtmp.conf)

```nginx
rtmp {
    server {
        listen ${RTMP_PORT};        # Puerto 1935 por defecto
        chunk_size 4096;
        allow publish all;
        
        application hls {
            live on;                 # Modo en vivo habilitado
            record off;              # Sin grabación
            
            hls on;                  # Habilitar transcodificación HLS
            hls_path /tmp/hls;      # Directorio para segmentos .ts
            hls_fragment 1;          # Duración de cada segmento (segundos)
            hls_playlist_length 2;  # Número de segmentos en la playlist
        }
    }
}
```

#### Parámetros Clave:

- **`listen ${RTMP_PORT}`**: Puerto donde Nginx acepta conexiones RTMP (1935)
- **`chunk_size 4096`**: Tamaño del chunk para la transferencia de datos
- **`application hls`**: Define una aplicación llamada "hls" que procesa streams
- **`hls on`**: Activa la conversión automática de RTMP a HLS
- **`hls_path /tmp/hls`**: Ruta donde se almacenan los segmentos .ts y archivos .m3u8

### 2.3 Configuración HTTP para HLS

Ubicación: [nginx/http.conf](nginx/http.conf)

```nginx
http {
    server {
        listen ${HTTP_PORT};
        
        location /hls {
            root /tmp;
            
            # Tipos MIME para HLS
            types {
                application/vnd.apple.mpegurl m3u8;
                video/mp2t ts;
            }
            
            add_header Access-Control-Allow-Origin *;
            add_header Cache-Control no-cache;
        }
    }
}
```

#### Flujo de Conversión RTMP → HLS:

```
1. Cliente RTMP (OBS) ──envía stream──▶ Nginx (puerto 1935)
2. Nginx RTMP module ──recibe flujo──▶ 
3. Transcodificador interno ──convierte a──▶ Segmentos .ts (1 segundo)
4. Generador playlist ──crea──▶ Archivo .m3u8
5. Cliente HTTP ──solicita──▶ Nginx (puerto 5555) ──entrega──▶ .m3u8 / .ts
```

### 2.4 Dockerfile de Nginx

Ubicación: [nginx/Dockerfile](nginx/Dockerfile)

El contenedor se construye con el módulo RTMP habilitado:

```dockerfile
FROM nginx:latest
RUN apt-get update && apt-get install -y nginx-full-modules-meta
```

---

## 3. Script Python para Captura de Stream

### 3.1 Propósito

El script Python se conecta al stream HLS generado por Nginx y permite:
- Capturar frames del video en vivo
- Procesar cada frame (detección de movimiento, análisis, etc.)
- Mostrar el stream en ventana de visualización

### 3.2 Código Fuente

Ubicación: [python_script/main.py](python_script/main.py)

```python
import cv2

hls_url = "http://localhost:5555/hls/my-stream.m3u8"

cap = cv2.VideoCapture(hls_url)

if not cap.isOpened():
    print("Error: no se pudo abrir el stream HLS")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("No hay frame (buffering o corte)")
        break

    cv2.imshow("HLS Stream", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 3.3 Funcionamiento Detallado

| Paso | Descripción |
|------|-------------|
| **1. URL del Stream** | `http://localhost:5555/hls/my-stream.m3u8`指向 Nginx生成的HLS播放列表 |
| **2. cv2.VideoCapture** | OpenCV se conecta al stream como si fuera un archivo de video local |
| **3. Lectura de Frames** | `cap.read()` obtiene cada frame del stream HLS |
| **4. Visualización** | `cv2.imshow()` muestra el frame en una ventana |
| **5. Control** | Presionar 'q' sale del bucle y cierra ventanas |

### 3.4 Dependencias

Ubicación: [python_script/requirements.txt](python_script/requirements.txt)

```
opencv-python
```

> **Nota**: OpenCV puede reproducir streams HLS nativamente en la mayoría de los casos, pero la estabilidad depende del códec utilizado.

---

## 4. Docker Compose - Orquestación

Ubicación: [docker-compose.yaml](docker-compose.yaml)

```yaml
services:
  nginx:
    image: nginx-i
    build:
      context: nginx
      dockerfile: Dockerfile
      args:
        ENABLED_MODULES: rtmp
    ports:
      - "${HTTP_PORT}:${HTTP_PORT}"    # 5555
      - "${RTMP_PORT}:${RTMP_PORT}"    # 1935
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf
      - ./nginx/rtmp.conf:/etc/nginx/templates/rtmp.conf.template
      - ./nginx/http.conf:/etc/nginx/templates/http.conf.template
```

### Puertos Expuestos:

| Puerto | Protocolo | Propósito |
|--------|-----------|-----------|
| **1935** | RTMP | Recepción de streams desde OBS/u otros |
| **5555** | HTTP | Entrega de archivos HLS (.m3u8, .ts) |

---

## 5. Frontend Angular - Reproducción

### 5.1 Componente VideoPlayer

Ubicación: [frontend/mi-app/src/app/video-player/](frontend/mi-app/src/app/video-player/)

El frontend utiliza **HLS.js** para reproducir el stream en el navegador:

```typescript
import Hls from 'hls.js';

if (Hls.isSupported()) {
  const hls = new Hls();
  hls.loadSource('http://localhost:5555/hls/my-stream.m3u8');
  hls.attachMedia(video);
}
```

### 5.2 Flujo Completo de Streaming

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   OBS        │     │   Nginx      │     │   Archivos   │     │  Angular    │
│  (Publicador)│────▶│   (RTMP:1935) │────▶│   HLS        │────▶│  (HLS.js)   │
│              │     │              │     │  (/tmp/hls)  │     │             │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    │
                            │                    ▼
                            │             ┌──────────────┐
                            │             │   Python     │
                            │             │   (OpenCV)   │
                            │             └──────────────┘
                            │
                            ▼
                     ┌──────────────┐
                     │  Python      │
                     │  Script      │
                     │  (Opcional)  │
                     └──────────────┘
```

---

## 6. Casos de Uso

### 6.1 Publicar Stream (OBS)
1. Configurar OBS → Servidor de streaming: `rtmp://localhost:1935/hls`
2. Clave de stream: cualquier valor
3. Nginx recibe el stream y lo convierte a HLS

### 6.2 Reproducir en Navegador
1. Angular carga `http://localhost:5555/hls/my-stream.m3u8`
2. HLS.js descarga segmentos y los reproduce

### 6.3 Procesar con Python
1. Ejecutar `python main.py`
2. OpenCV captura frames del stream HLS
3. Se puede agregar procesamiento (detección de objetos, etc.)

---

## 7. Variables de Entorno

Definidas en `.env`:

```env
NGINX_HOST=nginx-rtmp
HTTP_PORT=5555
RTMP_PORT=1935
```

---

## 8. Limitaciones y Mejoras

### Limitaciones Actuales:
- Solo un stream simultáneo (configuración básica)
- Sin autenticación en RTMP
- Sin transcodificación a múltiples calidades

### Mejoras Posibles:
- Implementar FFmpeg para múltiples resoluciones
- Agregar autenticación RTMP
- Almacenamiento de streams en disco
- API de control para iniciar/detener streams