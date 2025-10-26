FROM apache/airflow:2.8.3

COPY --chown=airflow:airflow deployment/airflow-requirements.txt /tmp/airflow-requirements.txt

RUN pip install --no-cache-dir -r /tmp/airflow-requirements.txt \
    && rm -f /tmp/airflow-requirements.txt
