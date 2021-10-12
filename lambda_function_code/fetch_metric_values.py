# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os
import boto3
import json
import logging

logging.basicConfig()

logger = logging.getLogger("lambda:fetch_metric_values")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))

events_client = boto3.client("events")


def lambda_handler(event, context):
    """
    This will just emit an event to the default bus
    Args:
        event (dict): The event from EventBridge
        context : the context
    """

    logger.info("Starting execution with payload:")
    logger.info(json.dumps(event))

    return events_client.put_events(
        Entries=[
            {
                "Source": "metric_fetch",
                "Resources": [],
                "DetailType": "metric_fetch",
                "Detail": "{}",
            }
        ]
    )
