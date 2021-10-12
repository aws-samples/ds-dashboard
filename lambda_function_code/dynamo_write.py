# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import json
import logging

logging.basicConfig()

logger = logging.getLogger("lambda:dynamo_write")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))


def lambda_handler(event, context):
    """This is meant to be automatically triggered by an EventBridge Rule
    an example event will be:
    ~~~python
    {
        'source': 'metric_extractor',
        'resources': [],
        'detail-type': 'metric_extractor',
        'detail': payload,
    }
    ~~~

    with payload being:

    ~~~python
    {
        "MetricName": metric_name,
        "MetricValue": metric_value,
        "ExtractionDate": extraction_date,
        "Metadata": metadata,
        "Environment": environment,
        "ProjectName": project_name
    }
    ~~~

    Args:
        event (dict): The event from EventBridge
        context : the context
    """

    logger.info("Starting execution with payload:")
    logger.info(json.dumps(event))

    ddb_table_name = os.getenv("DDB_TABLE_NAME")

    dynamodb = boto3.resource("dynamodb")

    table = dynamodb.Table(ddb_table_name)

    return table.put_item(Item=event["detail"])
