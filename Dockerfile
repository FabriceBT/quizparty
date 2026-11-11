# Fouquiz en production : docker build -t quizparty . && docker run -p 8000:8000 -v quizdata:/data quizparty
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
COPY static static
COPY templates templates
COPY seed seed
ENV QUIZ_DATA=/data PORT=8000
VOLUME /data
EXPOSE 8000
# Un seul processus (l'état des parties en direct est gardé en mémoire) ; --proxy-headers pour le HTTPS du fournisseur.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"]
