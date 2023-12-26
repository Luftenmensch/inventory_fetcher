FROM python:3.11

COPY requirements.txt /app/requirements.txt
WORKDIR /app
RUN pip install -r requirements.txt

COPY . /app

WORKDIR /app

CMD ["python", "main.py"]
