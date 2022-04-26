FROM python:3.10-alpine

RUN mkdir /app
COPY . /app
WORKDIR /app
RUN pip install flask requests
EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]