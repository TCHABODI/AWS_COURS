import json
import os
from http import client

import boto3


def lambda_handler(event, context):
    print("Event: ", json.dumps(event))
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda loaded from src/main.py!')
    }
def lambda_handler(event, context):
    print("Event: ", json.dumps(event))
    for r in event['Records']:
        if "object" in r.get("s3"):
            filename = r["s3"]["object"]["key"]
            print("Filename: ", filename)

    client = boto3.resource('dynamodb')
    table = client.Table(os.environ['TABLE_NAME'])
    response = table.get_item(Key={'PK': 'stchabodi'})
    if "Item" not in response :
        item = {"PK": "stchabodi", "filename": "test"}
        table.put_item(Item=item)
    print(f"Item: {item}")
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda loaded from src/main.py!')
    }
