import json

def lambda_handler(event, context):
    print("Event: ", json.dumps(event))
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda loaded from src/main.py!')
    }
