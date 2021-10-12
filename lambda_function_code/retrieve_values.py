# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from metric import *
import os
import logging

logging.basicConfig()

logger = logging.getLogger("lambda:retrieve_values")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))


def lambda_handler(event, context):
    """This loops on the metrics defined and calculates their values
    It requires PROJECT_NAME and ENVIRONMENT (dev/preprod/prod) in the environment

    Args:
        event (dict): the payload. not used
        context: the execution context
    """

    logger.info("Starting execution with payload:")
    logger.info(json.dumps(event))

    project_name = os.getenv("PROJECT_NAME")
    environment = os.getenv("ENVIRONMENT")
    metrics = os.getenv("METRIC_NAMES")

    if metrics is None:
        return

    metrics = metrics.split(",")

    for m in metrics:

        logger.info(f"Extracting value for metric {m}")

        args = {
            "project_name": project_name,
            "metric_name": m,
            "metadata": {},
            "environment": environment,
        }

        metric_class = eval(f"{m}")

        metric_instance = metric_class(**args)

        metric_value = metric_instance.extract()

        metric_instance.emit_event(metric_value)
