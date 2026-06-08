"""
# Devoir Final - Pipeline IoT Serverless
# Fichier   : index.py
# Role      : Fonction AWS Lambda d'ingestion de donnees IoT en temps reel
# Runtime   : Python 3.11
# Handler   : index.lambda_handler
#
# Flux de traitement :
#   1. Reception de la requete HTTP POST via API Gateway et CloudFront
#   2. Parse du payload JSON contenant la liste des mesures capteurs
#   3. Sauvegarde du payload brut dans S3 avec partitionnement temporel
#   4. Calcul de la temperature moyenne et comptage des anomalies ERROR
#   5. Enregistrement du rapport d'execution dans DynamoDB
#   6. Reponse HTTP 201 avec le resume de l'execution

import json
import os
import uuid
import boto3
import traceback
from datetime import datetime
from decimal import Decimal

# Initialisation des clients AWS SDK, executee une seule fois au cold-start
s3_client = boto3.client('s3')
dynamodb_resource = boto3.resource('dynamodb')


def lambda_handler(event: dict, context) -> dict:
    """
    Point d'entree principal de la Lambda.

    Args:
        event   : Evenement API Gateway (dict contenant body, headers, etc.)
        context : Contexte Lambda (aws_request_id, remaining_time, etc.)

    Returns:
        dict : Reponse HTTP formatee (statusCode, headers, body)
    """
    print(f"[START] Execution Lambda - request_id={context.aws_request_id}")
    print(f"[EVENT] {json.dumps(event)}")

    try:
        # Parse du corps JSON de la requete HTTP entrante
        raw_body = event.get('body') or '{}'
        body = json.loads(raw_body)

        records = body.get('records', [])
        if not isinstance(records, list) or len(records) == 0:
            raise ValueError(
                "Le champ 'records' est manquant, vide ou n'est pas une liste."
            )

        print(f"[PARSE] {len(records)} enregistrement(s) recu(s)")

        # Metadonnees de la requete
        now = datetime.utcnow()
        request_id = context.aws_request_id
        bucket_name = os.environ['S3_BUCKET']
        table_name = os.environ['DYNAMODB_TABLE']

        # Construction de la cle S3 avec partitionnement temporel Hive-compatible
        # Format : raw-zone/year=YYYY/month=MM/<request_id>.json
        s3_key = (
            f"raw-zone/"
            f"year={now.year}/"
            f"month={now.month:02d}/"
            f"{request_id}.json"
        )

        # Sauvegarde du payload brut dans S3
        s3_client.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(body, ensure_ascii=False, indent=2),
            ContentType='application/json',
            Metadata={
                'request-id': request_id,
                'record-count': str(len(records)),
                'ingestion-timestamp': now.isoformat()
            }
        )
        print(f"[S3] Fichier sauvegarde : s3://{bucket_name}/{s3_key}")

        # Calcul des metriques a la volee
        # Note : on ignore les enregistrements sans champ temperature ou avec None
        temperatures = [
            float(r['temperature'])
            for r in records
            if 'temperature' in r and r['temperature'] is not None
        ]

        avg_temperature = (
            round(sum(temperatures) / len(temperatures), 2)
            if temperatures
            else 0.0
        )

        error_count = sum(
            1 for r in records if r.get('status') == 'ERROR'
        )

        print(
            f"[METRICS] avg_temperature={avg_temperature}C | "
            f"error_count={error_count} | "
            f"total_records={len(records)}"
        )

        # Enregistrement du rapport dans DynamoDB
        # Remarque : boto3 refuse les types float natifs pour DynamoDB,
        # il faut passer par Decimal(str(valeur)) obligatoirement.
        table = dynamodb_resource.Table(table_name)
        item = {
            'request_id':      request_id,
            'timestamp':       now.isoformat() + 'Z',
            's3_path':         f"s3://{bucket_name}/{s3_key}",
            'avg_temperature': Decimal(str(avg_temperature)),
            'error_count':     error_count,
            'record_count':    len(records)
        }
        table.put_item(Item=item)
        print(f"[DYNAMODB] Rapport enregistre : request_id={request_id}")

        # Reponse de succes HTTP 201 (Created)
        response_body = {
            'request_id':      request_id,
            'message':         'Donnees ingererees avec succes',
            's3_path':         s3_key,
            'avg_temperature': avg_temperature,
            'error_count':     error_count,
            'record_count':    len(records),
            'timestamp':       now.isoformat() + 'Z'
        }

        print(f"[END] Succes - HTTP 201")
        return {
            'statusCode': 201,
            'headers': {
                'Content-Type':                'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response_body, ensure_ascii=False)
        }

    except json.JSONDecodeError as e:
        error_msg = f"Payload JSON invalide : {str(e)}"
        print(f"[ERROR-JSON] {error_msg}")
        traceback.print_exc()
        return _error_response(400, error_msg)

    except (KeyError, ValueError, TypeError) as e:
        error_msg = f"Donnees invalides ou champ manquant : {str(e)}"
        print(f"[ERROR-DATA] {error_msg}")
        traceback.print_exc()
        return _error_response(422, error_msg)

    except Exception as e:
        error_msg = f"Erreur interne du serveur : {str(e)}"
        print(f"[ERROR-INTERNAL] {error_msg}")
        traceback.print_exc()
        # On releve l'exception pour que CloudWatch enregistre le stack trace complet
        raise


def _error_response(status_code: int, message: str) -> dict:
    """Construit une reponse d'erreur HTTP standardisee."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type':                'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({'error': message}, ensure_ascii=False)
    }

