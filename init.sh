source venv/bin/activate

pip3 install -r requirements.txt

sls plugin install -n serverless-wsgi
sls plugin install -n serverless-python-requirements
sls plugin install -n serverless-dynamodb-local

sls dynamodb install