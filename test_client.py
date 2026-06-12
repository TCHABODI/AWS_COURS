# Devoir Final - Pipeline IoT Serverless
# Fichier : test_client.py
# Role    : Script de test client - simulation d'injection de donnees capteurs
#
# L'API utilise FastAPI + Mangum (comme dans le TP4).
# Comportement attendu par test :
#   Test 1 : payload valide          -> HTTP 201 (succes)
#   Test 2 : records vide []         -> ValueError dans Lambda -> HTTP 500 + stack trace CloudWatch
#   Test 3 : champ sensor_id absent  -> validation Pydantic    -> HTTP 422 (erreur geree)
#
# Usage :
#   pip install requests
#   python test_client.py

import requests
import json
from datetime import datetime, timezone

# URL du point d'entree CloudFront - a remplacer avec la valeur des Outputs CloudFormation
CLOUDFRONT_INGESTION_URL = "https://d3tterj62ysebo.cloudfront.net/ingest"

TIMEOUT_SECONDS = 30
HEADERS = {"Content-Type": "application/json"}


# Payload valide : 4 capteurs avec les cles sensor_id, temperature et status
# Ces cles sont requises par le modele Pydantic SensorRecord dans index.py
VALID_PAYLOAD = {
    "batch_id": "batch-test-20260609-001",
    "source":   "factory-line-A",
    "records": [
        {
            "sensor_id":   "sensor-001",
            "temperature": 72.5,
            "humidity":    45.2,
            "pressure":    1013.25,
            "status":      "OK",
            "timestamp":   "2026-06-09T10:00:00Z"
        },
        {
            "sensor_id":   "sensor-002",
            "temperature": 89.3,
            "humidity":    62.1,
            "pressure":    1012.80,
            "status":      "ERROR",
            "timestamp":   "2026-06-09T10:00:05Z"
        },
        {
            "sensor_id":   "sensor-003",
            "temperature": 68.1,
            "humidity":    41.0,
            "pressure":    1014.00,
            "status":      "OK",
            "timestamp":   "2026-06-09T10:00:10Z"
        },
        {
            "sensor_id":   "sensor-004",
            "temperature": 95.7,
            "humidity":    71.5,
            "pressure":    1011.50,
            "status":      "ERROR",
            "timestamp":   "2026-06-09T10:00:15Z"
        }
    ]
}

# Temperature moyenne attendue : (72.5 + 89.3 + 68.1 + 95.7) / 4 = 81.4 C
# Anomalies ERROR attendues    : 2


# Test 1 : payload valide (HTTP 201 attendu)
def test_valid_payload():
    """Envoie un payload de 4 capteurs valides et verifie la reponse HTTP 201."""
    sep = "-" * 65
    print(f"\n{sep}")
    print("  Test 1 : payload valide (HTTP 201 attendu)")
    print(sep)
    print(f"  URL cible : {CLOUDFRONT_INGESTION_URL}")
    print(f"  Capteurs  : {len(VALID_PAYLOAD['records'])}")
    print(f"  Envoi a   : {datetime.now(timezone.utc).isoformat()}")
    print(sep)

    try:
        response = requests.post(
            CLOUDFRONT_INGESTION_URL,
            json=VALID_PAYLOAD,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS
        )

        print(f"\n  Statut HTTP recu : {response.status_code}")

        if response.status_code == 201:
            result = response.json()
            print("  Succes - donnees ingerees correctement.")
            print(f"    request_id      : {result.get('request_id')}")
            print(f"    s3_path         : {result.get('s3_path')}")
            print(f"    avg_temperature : {result.get('avg_temperature')} C")
            print(f"    error_count     : {result.get('error_count')}")
            print(f"    record_count    : {result.get('record_count')}")
        else:
            print(f"  Echec - statut inattendu : {response.status_code}")
            print(f"  Reponse : {response.text[:500]}")

    except requests.exceptions.ConnectionError as e:
        print(f"  Erreur de connexion : {e}")
    except requests.exceptions.Timeout:
        print(f"  Delai d'attente depasse ({TIMEOUT_SECONDS}s)")
    except Exception as e:
        print(f"  Erreur inattendue : {e}")


# Test 2 : records vide -> ValueError dans l'endpoint FastAPI -> Lambda crash
# L'exception remonte via le global_exception_handler qui execute "raise",
# ce qui provoque un crash Lambda visible dans CloudWatch avec stack trace complet.
def test_empty_records():
    """
    Envoie un payload avec records=[] pour provoquer un ValueError dans la Lambda.
    Le gestionnaire global de FastAPI logue le stack trace et releve l'exception,
    ce qui fait crasher la Lambda et incremente la metrique Errors dans CloudWatch.
    """
    sep = "-" * 65
    print(f"\n{sep}")
    print("  Test 2 : records vide -> ValueError Lambda -> stack trace CloudWatch")
    print(sep)

    corrupt_payload = {
        "batch_id": "batch-corrupt-empty",
        "records": []
    }

    print(f"\n  Payload envoye : {json.dumps(corrupt_payload)}\n")

    try:
        response = requests.post(
            CLOUDFRONT_INGESTION_URL,
            json=corrupt_payload,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS
        )
        print(f"  Statut HTTP recu : {response.status_code}")
        print(f"  Reponse          : {response.text[:300]}")
        print("  -> Verifier /aws/lambda/stchabodi-iot-ingestion dans CloudWatch")
        print("     pour le stack trace Python complet du ValueError.")

    except Exception as e:
        print(f"  Erreur : {e}")


# Test 3 : champ sensor_id manquant -> validation Pydantic -> HTTP 422
# FastAPI detecte que le schema Pydantic n'est pas respecte et retourne
# une reponse 422 Unprocessable Entity sans que la Lambda crashe.
def test_pydantic_validation_error():
    """
    Envoie un enregistrement sans le champ sensor_id (requis par SensorRecord).
    Pydantic leve une ValidationError et FastAPI retourne HTTP 422 automatiquement.
    Le stack trace est visible dans CloudWatch mais la Lambda ne crashe pas.
    """
    sep = "-" * 65
    print(f"\n{sep}")
    print("  Test 3 : schema invalide (sensor_id manquant) -> HTTP 422 Pydantic")
    print(sep)

    # sensor_id est requis dans le modele SensorRecord mais absent ici
    invalid_payload = {
        "batch_id": "batch-schema-error",
        "records": [
            {
                "temperature": 55.0,
                "status": "OK"
            }
        ]
    }

    print(f"\n  Payload envoye :")
    print(json.dumps(invalid_payload, indent=4))
    print()

    try:
        response = requests.post(
            CLOUDFRONT_INGESTION_URL,
            json=invalid_payload,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS
        )
        print(f"  Statut HTTP recu : {response.status_code}")
        print(f"  Reponse          : {response.text[:400]}")

    except Exception as e:
        print(f"  Erreur : {e}")


if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  PIPELINE IoT SERVERLESS - SCRIPT DE TEST CLIENT")
    print("  FastAPI + Mangum + AWS Lambda")
    print("  Devoir Final Cloud Computing - Master 1")
    print("=" * 65)

    if "XXXXXXXXXXXXXXXXXX" in CLOUDFRONT_INGESTION_URL:
        print("\n  ATTENTION : CLOUDFRONT_INGESTION_URL n'est pas configuree.")
        print("  Remplacez-la par la valeur du Output CloudFormation.")
        print("  Exemple : https://d1abc2defg3hij.cloudfront.net/ingest\n")
        exit(1)

    test_valid_payload()
    test_empty_records()
    test_pydantic_validation_error()

    print("\n" + "=" * 65)
    print("  Tests termines - verifiez S3, DynamoDB et CloudWatch")
    print("=" * 65 + "\n")
