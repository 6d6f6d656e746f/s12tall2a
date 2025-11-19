FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# Working directory for Lambda
WORKDIR /var/task

# Copy requirements and install (including AWS Lambda RIC)
COPY requirements.txt .
# Instalar la versión de Playwright que coincide con la imagen base y el RIC de Lambda
RUN pip install --no-cache-dir playwright==1.35.0 awslambdaric && \
	pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Ensure Python output is not buffered
ENV PYTHONUNBUFFERED=1

# Crear directorios de cache de fuentes y configurar variables de entorno
RUN mkdir -p /tmp/.fontconfig /tmp/.cache/fontconfig && \
	chmod -R 777 /tmp/.fontconfig /tmp/.cache && \
	apt-get update && apt-get install -y --no-install-recommends fonts-liberation && \
	rm -rf /var/lib/apt/lists/*

ENV XDG_CACHE_HOME=/tmp/.cache
ENV FONTCONFIG_PATH=/tmp/.fontconfig

# Start the AWS Lambda Runtime Interface Client and point to the handler
ENTRYPOINT ["/usr/bin/python3", "-m", "awslambdaric"]
# Point to the handler inside the wsAWS package so the image uses the new implementation
CMD ["wsAWS.scrap_table.lambda_handler"]
