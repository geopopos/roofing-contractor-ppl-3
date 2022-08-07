import os
import uuid
import boto3
import dynamo
import json
import requests
from flask import Flask, jsonify, make_response, request
from urllib import parse

from botocore.exceptions import ClientError
ERROR_HELP_STRINGS = {
    # Common Errors
    'InternalServerError': 'Internal Server Error, generally safe to retry with exponential back-off',
    'ProvisionedThroughputExceededException': 'Request rate is too high. If you\'re using a custom retry strategy make sure to retry with exponential back-off.' +
                                              'Otherwise consider reducing frequency of requests or increasing provisioned capacity for your table or secondary index',
    'ResourceNotFoundException': 'One of the tables was not found, verify table exists before retrying',
    'ServiceUnavailable': 'Had trouble reaching DynamoDB. generally safe to retry with exponential back-off',
    'ThrottlingException': 'Request denied due to throttling, generally safe to retry with exponential back-off',
    'UnrecognizedClientException': 'The request signature is incorrect most likely due to an invalid AWS access key ID or secret key, fix before retrying',
    'ValidationException': 'The input fails to satisfy the constraints specified by DynamoDB, fix input before retrying',
    'RequestLimitExceeded': 'Throughput exceeds the current throughput limit for your account, increase account level throughput before retrying',
}

app = Flask(__name__)


dynamodb_client = boto3.client('dynamodb')
sqs_client = boto3.client('sqs')
roofing_api_url = "https://e6b1hc9rfg.execute-api.us-east-1.amazonaws.com"

if os.environ.get('IS_OFFLINE') == 'True':
    dynamodb_client = boto3.client(
        'dynamodb', region_name='localhost', endpoint_url='http://localhost:8000'
    )
    roofing_api_url = "http://localhost:2000"


PPL_TABLE = os.environ['PPL_TABLE']

@app.route('/roofer', methods=['POST'])
def create_roofer():
    print(os.environ)
    # print(request.environ)
    pk = f"Roofer#{str(uuid.uuid4())}"
    sk = "ROOFER"
    dynamo_data = dynamo.to_item(request.json) 
    print(f'::REQUEST:JSON ==> {request.json}')
    if not "Email" in request.json.keys():
        return jsonify({'error': 'Please provide key value pair with key "Email"'}), 400
    # check if email already exists in roofer db

    get_roofer_by_email_url = f"{roofing_api_url}/roofer/email/{parse.quote(request.json['Email'])}"
    response = requests.request("GET", get_roofer_by_email_url)

    print(response.text)
    
    roofer_record = json.loads(response.text)
    if roofer_record:
        roofer_record.update({'roofer_exists': True})
        return jsonify(roofer_record), 200

    dynamo_data['pk'] = {'S': pk}
    dynamo_data['sk'] = {'S': sk}
    dynamodb_client.put_item(
        TableName=PPL_TABLE, Item=dynamo_data
    )

    name = None
    if "First Name" in request.json.keys():
        name = f"{request.json['First Name']} {request.json['Last Name']}"
    email = request.json['Email']

    output_object = {
        'pk': pk,
        'sk': sk,
        'name': name,
        'email': email,
        'roofer_exists': False,
        'phone': request.json['Phone']
    }

    return jsonify(output_object), 201


@app.route('/roofer/<string:pk>', methods=['GET'])
def get_roofer(pk):
    sk = "ROOFER"
    input = {
        "TableName": PPL_TABLE,
        "KeyConditionExpression": "#bef90 = :bef90 And #bef91 = :bef91",
        "ExpressionAttributeNames": {"#bef90":"pk","#bef91":"sk"},
        "ExpressionAttributeValues": {":bef90": {"S":pk},":bef91": {"S":sk}}
    }
    try:
        response = dynamodb_client.query(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    item = response.get('Items', [])
    if not item:
        return jsonify({'error': 'Could not find roofer with provided "pk"'})
    item = item[0]

    dict_data = dynamo.to_dict(item)

    return jsonify(
        dict_data
    )

@app.route('/roofer/', methods=['GET'])
def get_all_roofers():
    input = {
        "TableName": PPL_TABLE,
        "FilterExpression": "#766a0 = :766a0",
        "ExpressionAttributeNames": {"#766a0":"sk"},
        "ExpressionAttributeValues": {":766a0": {"S":"ROOFER"}}
    }
    try:
        response = dynamodb_client.scan(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    items = response.get('Items', [])
    if not items:
        return jsonify({'error': 'Could not find any roofers'})
    dict_data = []
    for item in items:
        dict_data.append(dynamo.to_dict(item))

    return jsonify(
        dict_data
    )

@app.route('/roofer/<string:pk>', methods=['PUT'])
def update_roofer(pk):
    update_data = request.json
    sk = "ROOFER"
    # input = {
    #     "TableName": PPL_TABLE,
    #     "Key": {
    #         "pk": {"S": pk },
    #         "sk": {"S":sk}
    #     },
    #     "UpdateExpression": "SET #7b390 = :7b390",
    #     "ExpressionAttributeNames": {"#7b390":"StripeId"},
    #     "ExpressionAttributeValues": {":7b390": {"S":stripe_id}}
    # }
    # response = dynamodb_client.query(**input)
    update_expression = "SET "
    expression_attribute_values = {}
    for k, v in update_data.items():
        update_expression += f"{k} = :{k},"
        expression_attribute_values[f":{k}"] = {"S": v}
    # remove last comma from update expression
    update_expression = update_expression[:-1]
    print(expression_attribute_values)
    response = dynamodb_client.update_item(
        TableName=PPL_TABLE,
        Key={'pk': {'S': pk}, 'sk': {'S': sk}},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="UPDATED_NEW"
    )
    print("Query successful.")

    attributes = response.get('Attributes')
    if not attributes:
        return jsonify({'error': 'Could not find user with provided "pk"'}), 404

    dict_data = dynamo.to_dict(attributes)

    return jsonify(
        dict_data
    )



@app.route('/lead', methods=['POST'])
def create_lead():
    pk = f"Lead#{str(uuid.uuid4())}"
    sk = "LEAD"
    dynamo_data = dynamo.to_item(request.json) 

    dynamo_data['pk'] = {'S': pk}
    dynamo_data['sk'] = {'S': sk}
    dynamodb_client.put_item(
        TableName=PPL_TABLE, Item=dynamo_data
    )

    return jsonify({'pk': pk, 'sk':sk, 'data': request.json})

@app.route('/lead/<string:pk>', methods=['PUT'])
def update_lead(pk):
    update_data = request.json
    sk = "LEAD"
    update_expression = "SET "
    expression_attribute_values = {}
    for k, v in update_data.items():
        update_expression += f"{k} = :{k},"
        expression_attribute_values[f":{k}"] = {"S": v}
    # remove last comma from update expression
    update_expression = update_expression[:-1]
    print(expression_attribute_values)
    response = dynamodb_client.update_item(
        TableName=PPL_TABLE,
        Key={'pk': {'S': pk}, 'sk': {'S': sk}},
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="UPDATED_NEW"
    )
    print("Query successful.")

    attributes = response.get('Attributes')
    if not attributes:
        return jsonify({'error': 'Could not find lead with provided "pk"'}), 404

    dict_data = dynamo.to_dict(attributes)

    return jsonify(
        dict_data
    )

@app.route('/lead/<string:pk>', methods=['GET'])
def get_lead(pk):
    sk = "LEAD"
    input = {
        "TableName": PPL_TABLE,
        "KeyConditionExpression": "#bef90 = :bef90 And #bef91 = :bef91",
        "ExpressionAttributeNames": {"#bef90":"pk","#bef91":"sk"},
        "ExpressionAttributeValues": {":bef90": {"S":pk},":bef91": {"S":sk}}
    }
    try:
        response = dynamodb_client.query(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    item = response.get('Items')[0]
    if not item:
        return jsonify({'error': 'Could not find user with provided "pk"'}), 404

    dynamo_data = dynamo.to_dict(item)

    return jsonify(
        dynamo_data
    )


@app.route('/lead_purchase', methods=['POST'])
def create_lead_purchase():
    pk = request.json.pop('roofer')
    sk = request.json.pop('lead')
    dynamo_data = dynamo.to_item(request.json) 

    if not pk or not sk:
        return jsonify({'error': 'Please provide both "pk" and "data"'}), 400

    dynamo_data['pk'] = {'S': pk}
    dynamo_data['sk'] = {'S': sk}

    dynamodb_client.put_item(
        TableName=PPL_TABLE, Item=dynamo_data
    )

    return jsonify({'pk': pk, 'sk':sk, 'success': True})

@app.route('/roofer/lead/<string:pk>', methods=['GET'])
def get__roofer_leads(pk):
    input = {
        "TableName": PPL_TABLE,
        "KeyConditionExpression": "#69240 = :69240",
        "ExpressionAttributeNames": {"#69240":"pk"},
        "ExpressionAttributeValues": {":69240": {"S":pk}}
    }
    try:
        response = dynamodb_client.query(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    items = response.get('Items')
    if not items:
        return jsonify([])

    lead_purchases = list((x for x in items if x.get('sk').get('S') != 'ROOFER'))
    leads = []

    for i in lead_purchases:
        leads.append(dynamo.to_dict(i))

    return jsonify(
        leads
            )

@app.route('/roofer/email/<string:email>', methods=['GET'])
def get_roofer_by_email(email):
    input = {
        "TableName": PPL_TABLE,
        "IndexName": "Email",
        "KeyConditionExpression": "#84ad0 = :84ad0",
        "ExpressionAttributeNames": {"#84ad0":"Email"},
        "ExpressionAttributeValues": {":84ad0": {"S":email}}
    }
    try:
        response = dynamodb_client.query(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    try:
        item = response.get('Items')[0]
    except IndexError:
        return jsonify([])
    if not item:
        return jsonify({'error': 'Could not find user with provided "email"'}), 404

    dict_data = dynamo.to_dict(item)

    return jsonify(
        dict_data
    ), 200

@app.route('/roofer/stripe_id/<string:StripeId>', methods=['GET'])
def get_roofer_by_stripe_id(StripeId):
    input = {
        "TableName": PPL_TABLE,
        "IndexName": "StripeId",
        "KeyConditionExpression": "#84ad0 = :84ad0",
        "ExpressionAttributeNames": {"#84ad0":"StripeId"},
        "ExpressionAttributeValues": {":84ad0": {"S":StripeId}}
    }
    try:
        response = dynamodb_client.query(**input)
        print("Query successful.")
        # Handle response
    except ClientError as error:
        handle_error(error)
    except BaseException as error:
        print("Unknown error while querying: " + error.response['Error']['Message'])

    item = response.get('Items')[0]
    if not item:
        return jsonify({'error': 'Could not find user with provided "email"'}), 404

    dict_data = dynamo.to_dict(item)

    return jsonify(
        dict_data
    )

@app.errorhandler(404)
def resource_not_found(e):
    return make_response(jsonify(error='Not found!'), 404)


def handle_error(error):
    error_code = error.response['Error']['Code']
    error_message = error.response['Error']['Message']

    error_help_string = ERROR_HELP_STRINGS[error_code]

    print('[{error_code}] {help_string}. Error message: {error_message}'
          .format(error_code=error_code,
                  help_string=error_help_string,
                  error_message=error_message))