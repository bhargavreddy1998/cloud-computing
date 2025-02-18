import boto3
import csv
from flask import Flask, request

app = Flask(__name__)

ASU_ID = "1226491476"
S3_BUCKET_NAME = f"{ASU_ID}-in-bucket"
SDB_DOMAIN_NAME = f"{ASU_ID}-simpleDB"
REGION = 'us-east-1' 

s3_client = boto3.client("s3", region_name=REGION)
sdb_client = boto3.client("sdb", region_name=REGION)

def upload_image_to_s3(file, filename):
    s3_client.upload_fileobj(file, S3_BUCKET_NAME, filename)
    return f"s3://{S3_BUCKET_NAME}/{filename}"

def populate_simpledb():
    sdb_client.create_domain(DomainName=SDB_DOMAIN_NAME)
    with open('/Classification Results on Face Dataset (1000 images).csv', 'r', newline='') as csv_file:
        reader = csv.reader(csv_file)
        for row in reader:
            if not row:
                continue 
            image_name = row[0].strip()
            prediction = row[1].strip()
            print(image_name)
            print(prediction)
            print(image_name!="Image" and prediction!="Prediction")
            if image_name!="Image" and prediction!="Prediction":
                sdb_client.put_attributes(DomainName=SDB_DOMAIN_NAME, ItemName=image_name, 
                    Attributes=[
                        {
                            'Name': 'recognition',
                            'Value': prediction,
                            'Replace': True
                        }
                    ]
                )

@app.route("/", methods=["POST"])
def handle_post():
    if "inputFile" not in request.files:
        return "Error: No 'inputFile' key in request.\n", 400
    file_obj = request.files["inputFile"]
    filename = file_obj.filename.split('.')[0]
    try:
        upload_image_to_s3(file_obj, filename)
        response = sdb_client.get_attributes(DomainName=SDB_DOMAIN_NAME, ItemName=filename, ConsistentRead=True)
        if "Attributes" in response:
            for attr in response["Attributes"]:
                if attr["Name"] == "recognition":
                    prediction = attr["Value"]
                    break
                else:
                    prediction = "Unknown"
        else:
            prediction = "Unknown"
        return f"{filename}:{prediction}\n", 200

    except Exception as e:
        return f"Error processing the request: {str(e)}\n", 500

if __name__ == "__main__":
    populate_simpledb()
    app.run(host="0.0.0.0", port=8000, threaded=True)
