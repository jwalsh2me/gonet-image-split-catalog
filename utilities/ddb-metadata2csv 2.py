
import boto3
import json
import os
import pandas as pd
import datetime as dt

# TABLE_NAME = os.environ.get("DDB_TABLE_NAME")
TABLE_NAME = "gonet-image-metadata-v2"
# OUTPUT_BUCKET = os.environ.get("BUCKET_NAME")
TEMP_FILENAME = '/tmp/export.csv'
# OUTPUT_KEY = 'export.csv'

s3_resource = boto3.resource('s3')
dynamodb_resource = boto3.resource('dynamodb')
table = dynamodb_resource.Table(TABLE_NAME)


# def lambda_handler(event, context):
response = table.scan()
df = pd.DataFrame(response['Items'])
print(f"Items           |           Count\n{df.count()}")
print(f"\nRecord Count is:  {len(df.index)}")
df.to_csv(TEMP_FILENAME, index=False, header=True)

    # Upload temp file to S3
# s3_resource.Bucket(OUTPUT_BUCKET).upload_file(TEMP_FILENAME, OUTPUT_KEY)

# return {
#     'statusCode': 200,
#     'headers': {
#         "Access-Control-Allow-Origin": "*",
#         "Access-Control-Allow-Credentials": True,
#         "content-type": "application/json"
#     },
#     'body': json.dumps('OK')
# }