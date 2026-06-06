FROM python:3.10 AS final
EXPOSE 8888

RUN apt-get update \
    && apt-get install -y g++ git graphviz make pandoc texlive-xetex \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-notebooks.txt .
RUN pip install -r requirements-notebooks.txt

ENTRYPOINT ["jupyter"]
CMD ["lab", "--ip=0.0.0.0"]