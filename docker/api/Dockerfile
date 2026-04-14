FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    acl \
    mount \
    passwd \
    procps \
    samba-common-bin \
    util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY scc.py /app/scc.py
COPY scc_app/ /app/scc_app/

EXPOSE 8080

CMD ["python", "-u", "/app/scc.py", "serve", "0.0.0.0", "8080"]
