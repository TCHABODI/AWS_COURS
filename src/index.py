# Devoir Final - Pipeline IoT Serverless
# Fichier   : index.py
# Role      : Application FastAPI d'ingestion de donnees IoT
#             Deployee dans AWS Lambda via le wrapper Mangum (meme approche que TP4)
# Handler   : index.lambda_handler  <- Mangum encapsule FastAPI pour Lambda

import json
import os
import uuid
import boto3
import traceback
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from fastapi import FastAPI, Request
from mangum import Mangum
from pydantic import BaseModel

# Clients AWS SDK initialises une seule fois au cold-start Lambda
s3_client = boto3.client("s3")
dynamodb_resource = boto3.resource("dynamodb")


# ---------------------------------------------------------------------------
# Modeles Pydantic - FastAPI valide automatiquement le schema du payload
# ---------------------------------------------------------------------------

class SensorRecord(BaseModel):
    sensor_id: str
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    pressure: Optional[float] = None
    status: str
    timestamp: Optional[str] = None


class IoTPayload(BaseModel):
    batch_id: Optional[str] = None
    source: Optional[str] = None
    records: List[SensorRecord]


# ---------------------------------------------------------------------------
# Application FastAPI
# ---------------------------------------------------------------------------

app = FastAPI(
    title="IoT Ingestion Pipeline",
    description="API d'ingestion de donnees capteurs IoT en temps reel",
    version="1.0.0",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Gestionnaire global d'exceptions non gerees.
    Logue le stack trace complet dans CloudWatch puis releve l'exception
    pour que Lambda l'enregistre comme erreur (metrique Errors incrementee).
    """
    print(f"[ERROR-INTERNAL] {type(exc).__name__}: {exc}")
    traceback.print_exc()
    raise exc


@app.get("/health")
async def health_check():
    """Endpoint de sante - verifie que l'API est operationnelle."""
    return {"status": "ok", "service": "iot-ingestion-pipeline"}


@app.post("/ingest", status_code=201)
async def ingest_iot_data(payload: IoTPayload, request: Request):
    """
    Endpoint principal d'ingestion IoT.

    Pydantic valide automatiquement le schema du payload (types, champs requis).
    La fonction realise ensuite :
      1. Sauvegarde brute dans S3 avec partitionnement temporel Hive
      2. Calcul de la temperature moyenne et du nombre d'anomalies ERROR
      3. Enregistrement du rapport dans DynamoDB (Feature Store)
    """
    # Recuperation du request_id depuis le contexte Lambda via Mangum
    aws_context = request.scope.get("aws.context")
    request_id = aws_context.aws_request_id if aws_context else str(uuid.uuid4())

    records = payload.records
    if not records:
        raise ValueError("Le champ 'records' est vide - aucun enregistrement a ingerer")

    now = datetime.utcnow()
    bucket_name = os.environ["S3_BUCKET"]
    table_name = os.environ["DYNAMODB_TABLE"]

    print(f"[START] request_id={request_id} | {len(records)} enregistrement(s)")

    # Cle S3 avec partitionnement temporel Hive-compatible
    # Format : raw-zone/year=YYYY/month=MM/<request_id>.json
    s3_key = (
        f"raw-zone/"
        f"year={now.year}/"
        f"month={now.month:02d}/"
        f"{request_id}.json"
    )

    # Sauvegarde du payload brut dans S3 (Data Lake)
    # model_dump() est l'API Pydantic v2 ; fallback dict() pour Pydantic v1
    payload_dict = payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    s3_client.put_object(
        Bucket=bucket_name,
        Key=s3_key,
        Body=json.dumps(payload_dict, ensure_ascii=False, default=str),
        ContentType="application/json",
        Metadata={
            "request-id": request_id,
            "record-count": str(len(records)),
            "ingestion-timestamp": now.isoformat(),
        },
    )
    print(f"[S3] Fichier sauvegarde : s3://{bucket_name}/{s3_key}")

    # Calcul des metriques a la volee
    temperatures = [r.temperature for r in records if r.temperature is not None]
    avg_temperature = (
        round(sum(temperatures) / len(temperatures), 2) if temperatures else 0.0
    )
    error_count = sum(1 for r in records if r.status == "ERROR")

    print(
        f"[METRICS] avg_temperature={avg_temperature}C | "
        f"error_count={error_count} | "
        f"record_count={len(records)}"
    )

    # Enregistrement du rapport dans DynamoDB
    # Remarque : boto3 refuse les float natifs Python pour DynamoDB,
    # on utilise Decimal(str(valeur)) obligatoirement.
    table = dynamodb_resource.Table(table_name)
    table.put_item(
        Item={
            "request_id":      request_id,
            "timestamp":       now.isoformat() + "Z",
            "s3_path":         f"s3://{bucket_name}/{s3_key}",
            "avg_temperature": Decimal(str(avg_temperature)),
            "error_count":     error_count,
            "record_count":    len(records),
        }
    )
    print(f"[DYNAMODB] Rapport enregistre : request_id={request_id}")
    print(f"[END] Succes - HTTP 201")

    return {
        "request_id":      request_id,
        "message":         "Donnees ingerees avec succes",
        "s3_path":         s3_key,
        "avg_temperature": avg_temperature,
        "error_count":     error_count,
        "record_count":    len(records),
        "timestamp":       now.isoformat() + "Z",
    }


# Mangum adapte l'application FastAPI pour l'execution dans AWS Lambda.
# C'est ce lambda_handler qui est appele par API Gateway a chaque requete.
lambda_handler = Mangum(app, lifespan="off")
