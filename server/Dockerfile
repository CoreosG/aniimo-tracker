FROM python:3.13-slim
WORKDIR /app
COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY src/party_server.py src/party_protocol.py src/map_catalog.py /app/
USER 10001:10001
EXPOSE 8787
CMD ["python", "party_server.py", "--host", "0.0.0.0"]
