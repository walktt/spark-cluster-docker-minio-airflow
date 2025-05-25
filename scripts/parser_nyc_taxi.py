import requests
import boto3
from botocore.client import Config
import botocore
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Настройки MinIO ===
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "minio"
MINIO_SECRET_KEY = "minio123"
TAXI_TYPE = "green"
MINIO_BUCKET = f"nyc-taxi-{TAXI_TYPE}"
YEARS = range(2024, 2026)
MONTHS = range(1, 13)

def ensure_bucket_exists(s3, bucket):
    """Гарантированно создаёт bucket, если он не существует."""
    try:
        s3.head_bucket(Bucket=bucket)
        logger.info(f"Bucket '{bucket}' уже существует.")
    except botocore.exceptions.ClientError as e:
        code = e.response['Error']['Code']
        if code in ("404", "NoSuchBucket"):
            s3.create_bucket(Bucket=bucket)
            logger.info(f"Bucket '{bucket}' создан.")
        else:
            logger.error(f"Ошибка доступа к bucket '{bucket}': {e}")
            raise

def object_exists(s3, bucket, object_name):
    """Проверяет, существует ли объект в bucket (чтобы не скачивать заново)."""
    try:
        s3.head_object(Bucket=bucket, Key=object_name)
        return True
    except botocore.exceptions.ClientError as e:
        if e.response['Error']['Code'] in ("404", "NoSuchKey"):
            return False
        else:
            raise

def download_and_upload_to_minio(bucket: str, taxi_type: str, years, months):
    s3 = boto3.client(
        "s3",
        endpoint_url=MINIO_ENDPOINT,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        config=Config(signature_version="s3v4"),
    )
    logger.info(f"Инициализирован клиент MinIO: {s3}")

    ensure_bucket_exists(s3, bucket)

    for year in years:
        for month in months:
            taxi_url = f"https://d37ci6vzurychx.cloudfront.net/trip-data/{taxi_type}_tripdata_{year}-{month:02d}.parquet"
            object_name = taxi_url.split('/')[-1]

            if object_exists(s3, bucket, object_name):
                logger.info(f"Файл {object_name} уже есть в bucket, пропускаем.")
                continue

            logger.info(f"Скачиваем {taxi_url}")
            try:
                with requests.get(taxi_url, stream=True, timeout=60) as r:
                    if r.status_code == 404:
                        logger.warning(f"Файл {taxi_url} не найден (404), пропускаем.")
                        continue
                    r.raise_for_status()
                    s3.upload_fileobj(r.raw, bucket, object_name)
                    logger.info(f"Загружено: {object_name} в bucket {bucket}")
            except Exception as e:
                logger.error(f"Ошибка при скачивании/загрузке {object_name}: {e}")

if __name__ == "__main__":
    download_and_upload_to_minio(
        bucket=MINIO_BUCKET,
        taxi_type=TAXI_TYPE,
        years=YEARS,
        months=MONTHS
    )
