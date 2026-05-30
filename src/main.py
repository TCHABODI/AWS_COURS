import json
import os
import boto3

# Variables d'environnement injectées par CloudFormation
TABLE_NAME  = os.environ.get('TABLE_NAME', 's3-trigger-db')
ENV_NAME    = os.environ.get('ENV_NAME', 'dev')
BUCKET_NAME = os.environ.get('BUCKET_NAME', '')

# Extensions d'images autorisées
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}

dynamodb = boto3.resource('dynamodb')
table    = dynamodb.Table(TABLE_NAME)

def is_image(key: str) -> bool:
    """Vérifie si le fichier est une image selon son extension."""
    ext = os.path.splitext(key)[1].lower()
    return ext in ALLOWED_EXTENSIONS

def file_exists(filename: str) -> bool:
    """Vérifie si le fichier existe déjà dans DynamoDB."""
    response = table.get_item(Key={'PK': filename})
    return 'Item' in response

def lambda_handler(event, context):
    print("Event: ", json.dumps(event))

    for record in event.get('Records', []):
        filename = record['s3']['object']['key']
        bucket   = record['s3']['bucket']['name']
        size     = record['s3']['object'].get('size', 0)

        print(f"Fichier détecté : {filename}")

        # 1. Vérifier que c'est une image
        if not is_image(filename):
            print(f"Ignoré (non image) : {filename}")
            continue

        # 2. Vérifier si le fichier existe déjà en base
        if file_exists(filename):
            print(f"Fichier déjà présent en base, ignoré : {filename}")
            continue

        # 3. Ajouter le fichier dans DynamoDB
        item = {
            'PK'      : filename,
            'bucket'  : bucket,
            'filename': filename,
            'size'    : size,
        }
        table.put_item(Item=item)
        print(f"Fichier ajouté en base : {item}")

    return {
        'statusCode': 200,
        'body': json.dumps('Traitement terminé.')
    }
