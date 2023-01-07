import boto3
import botocore
import pandas as pd
from datetime import datetime
from botocore.exceptions import ClientError

client = boto3.client('dynamodb')
td = datetime.today().strftime('%Y-%m-%d')
TABLE_NAME = "gonet-image-metadata"
TEMP_FILENAME = f'../scratch/{td}_{TABLE_NAME}_export.csv'
# TEMP_FILENAME = f'/tmp/{td}_{TABLE_NAME}_export.csv'

def dump_table(table_name):
    results = []
    last_evaluated_key = None
    while True:
        if last_evaluated_key:
            response = client.scan(
                TableName=table_name,
                ExclusiveStartKey=last_evaluated_key
            )
        else:
            response = client.scan(TableName=table_name)
        last_evaluated_key = response.get('LastEvaluatedKey')

        results.extend(response['Items'])

        if not last_evaluated_key:
            break
    return results


try:
    data = dump_table(TABLE_NAME)
    print(f"Items in list:   {len(data)}")
except botocore.exceptions.ClientError as e:
    print(f"ERROR! - {e}")
df = pd.DataFrame(data)
print(f"Items           |             Count\n{df.count()}")
print(f"\nRecord Count is:  {len(df.index)}")
df.to_csv(TEMP_FILENAME, index=False, header=True)
print(f"Exported to: {TEMP_FILENAME}")
