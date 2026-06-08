# Devoir Final - Pipeline IoT Serverless
# Fichier : test_client.py
# Role    : Script de test client - simulation d'injection de donnees capteurs
#
# Usage :
#   1. Remplacez CLOUDFRONT_INGESTION_URL par l'URL CloudFront recuperee dans
#      les Outputs de la pile CloudFormation.
#   2. Installez la dependance : pip install requests
#   3. Executez : python test_client.py

import requests
import json
from datetime import datetime, timezone

# URL du point d'entree CloudFront - a remplacer avec la valeur des Outputs CloudFormation
CLOUDFRONT_INGESTION_URL = "https://XXXXXXXXXXXXXXXXXX.cloudfront.net/ingest"
# Exemple : "https://d1abc2defg3hij.cloudfront.net/ingest"

TIMEOUT_SECONDS = 30
HEADERS = {"Content-Type": "application/json"}


# Payload valide representant 4 capteurs IoT.
# Chaque enregistrement contient les cles obligatoires : sensor_id, temperature, status.
VALID_PAYLOAD = {
    "batch_id": "batch-test-20260608-001",
    "source":   "factory-line-A",
    "records": [
        {
            "sensor_id":   "sensor-001",
            "temperature": 72.5,
            "humidity":    45.2,
            "pressure":    1013.25,
            "status":      "OK",
            "timestamp":   "2026-06-08T10:00:00Z"
        },
        {
            "sensor_id":   "sensor-002",
            "temperature": 89.3,
            "humidity":    62.1,
            "pressure":    1012.80,
            "status":      "ERROR",
            "timestamp":   "2026-06-08T10:00:05Z"
        },
        {
            "sensor_id":   "sensor-003",
            "temperature": 68.1,
            "humidity":    41.0,
            "pressure":    1014.00,
            "status":      "OK",
            "timestamp":   "2026-06-08T10:00:10Z"
        },
        {
            "sensor_id":   "sensor-004",
            "temperature": 95.7,
            "humidity":    71.5,
            "pressure":    1011.50,
            "status":      "ERROR",
            "timestamp":   "2026-06-08T10:00:15Z"
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
    print(f"  URL cible   : {CLOUDFRONT_INGESTION_URL}")
    print(f"  Capteurs    : {len(VALID_PAYLOAD['records'])}")
    print(f"  Envoi a     : {datetime.now(timezone.utc).isoformat()}")
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
            print(f"  Echec - statut HTTP inattendu : {response.status_code}")
            print(f"  Reponse brute : {response.text[:500]}")

    except requests.exceptions.ConnectionError as e:
        print(f"  Erreur de connexion : {e}")
    except requests.exceptions.Timeout:
        print(f"  Delai d'attente depasse ({TIMEOUT_SECONDS}s)")
    except Exception as e:
        print(f"  Erreur inattendue : {e}")


# Test 2 : payload corrompu avec temperature invalide (type chaine non convertible).
# Objectif : provoquer un ValueError dans la Lambda (float("INVALIDE") echoue)
# et generer un stack trace Python visible dans CloudWatch Logs.
def test_corrupt_payload():
    """
    Envoie un payload dont les temperatures sont des chaines invalides.
    Le float() sur une chaine non numerique leve un ValueError dans Lambda,
    ce qui est releve (raise) et genere un rapport d'erreur complet dans CloudWatch.
    """
    sep = "-" * 65
    print(f"\n{sep}")
    print("  Test 2 : payload corrompu - temperatures invalides (type string)")
    print("           Objectif : ValueError dans Lambda -> stack trace CloudWatch")
    print(sep)

    # Les valeurs de temperature sont des chaines non convertibles en float.
    # Cela provoque : ValueError: could not convert string to float: 'SURCHAUFFE'
    corrupt_payload = {
        "batch_id": "batch-corrupt-002",
        "records": [
            {
                "sensor_id":   "sensor-bad-A",
                "temperature": "SURCHAUFFE_CRITIQUE",
                "status":      "ERROR"
            },
            {
                "sensor_id":   "sensor-bad-B",
                "temperature": "N/A",
                "status":      "ERROR"
            }
        ]
    }

    print(f"\n  Payload envoye :")
    print(json.dumps(corrupt_payload, indent=4))
    print()

    try:
        response = requests.post(
            CLOUDFRONT_INGESTION_URL,
            json=corrupt_payload,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS
        )
        print(f"  Statut HTTP recu : {response.status_code}")
        print(f"  Reponse          : {response.text[:300]}")
        print("  -> Verifier le groupe de logs /aws/lambda/<nom_fonction> dans CloudWatch")
        print("     pour voir le stack trace Python complet de ce ValueError.")

    except Exception as e:
        print(f"  Erreur : {e}")


# Test 3 : JSON syntaxiquement invalide (HTTP 400 attendu).
# Objectif : provoquer un json.JSONDecodeError dans Lambda
# et verifier que la gestion d'erreur retourne bien HTTP 400.
def test_malformed_json():
    """
    Envoie une chaine brute syntaxiquement invalide.
    json.loads() leve un JSONDecodeError dans Lambda (retourne HTTP 400).
    Le stack trace est visible dans CloudWatch Logs.
    """
    sep = "-" * 65
    print(f"\n{sep}")
    print("  Test 3 : JSON syntaxiquement invalide (HTTP 400 attendu)")
    print(sep)

    malformed_string = '{"records": [{ "sensor_id": "s1", "temperature": !!BAD'
    print(f"\n  Corps envoye : {malformed_string}\n")

    try:
        response = requests.post(
            CLOUDFRONT_INGESTION_URL,
            data=malformed_string,
            headers=HEADERS,
            timeout=TIMEOUT_SECONDS
        )
        print(f"  Statut HTTP recu : {response.status_code}")
        print(f"  Reponse          : {response.text[:300]}")

    except Exception as e:
        print(f"  Erreur : {e}")


# =============================================================================
# POINT D'ENTRÉE
# =============================================================================
if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("  PIPELINE IoT SERVERLESS - SCRIPT DE TEST CLIENT")
    print("  Devoir Final Cloud Computing - Master 1")
    print("=" * 65)

    if "XXXXXXXXXXXXXXXXXX" in CLOUDFRONT_INGESTION_URL:
        print("\n  ATTENTION : la variable CLOUDFRONT_INGESTION_URL n'est pas configuree.")
        print("  Remplacez-la par l'URL CloudFront presente dans les Outputs CloudFormation.")
        print("  Exemple : https://d1abc2defg3hij.cloudfront.net/ingest\n")
        exit(1)

    test_valid_payload()
    test_corrupt_payload()
    test_malformed_json()

    print("\n" + "=" * 65)
    print("  Tests termines - verifiez S3, DynamoDB et CloudWatch")
    print("=" * 65 + "\n")
