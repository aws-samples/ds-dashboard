# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import boto3
import json
import os
import logging

logging.basicConfig()

logger = logging.getLogger("lambda:dashboard_connection")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))


ssm_client = boto3.client("ssm")
event_client = boto3.client("events")


def flatten_parameters(parameters):
    """This takes a hierarchy of parameters as obtained from the SSM parameter store,
    and flattens it in simple key/value pairs {"AccountID1": "ProjectName1", ...}

    Args:
        parameters (dict): the parameters obtained from the SSM

    Returns:
        [dict]: a flat dictionary with account ids and project names
    """

    accounts = {}

    for p in parameters:
        p_account = p["Value"]
        accounts[p_account] = {}
        # separator for values is ;
        p_name = p["Name"].split("/")[2]
        accounts[p_account] = p_name

    return accounts


def allow_event_puts(account_id):
    """allows event puts from the account_id

    Args:
        account_id (str): the AWS account id
    """

    return event_client.put_permission(
        EventBusName="default",
        Action="events:PutEvents",
        Principal=account_id,
        StatementId=account_id,
    )


def forward_events(account_id, pattern, name_tag):
    """This creates an EventBridge rule to forward events to the target account id

    Args:
        account_id (str): The target AWS account id
    """

    put_rule_response = event_client.put_rule(
        Name=f"forwardTo{account_id}{name_tag}",
        EventPattern=json.dumps(pattern),
        State="ENABLED",
        Description=f"forwardTo{account_id}{name_tag}",
    )

    if put_rule_response["ResponseMetadata"]["HTTPStatusCode"] not in [200, 204]:
        return put_rule_response

    logger.debug("Response from PutRule:")
    logger.debug(put_rule_response)

    bus_arn = f'arn:aws:events:{os.getenv("AWS_REGION", "eu-west-1")}:{account_id}:event-bus/default'

    target = {"Arn": bus_arn, "Id": f"{account_id}-bus"}

    put_target_response = event_client.put_targets(
        Rule=f"forwardTo{account_id}{name_tag}", Targets=[target]
    )

    logger.debug("Response from PutTargets:")
    logger.debug(put_target_response)

    return put_target_response


def lambda_handler(event, context):
    """This is the main handler. It will be called with a payload
    specifying if it needs to configure the eventbus resource policy
    or if it has to create rolues to forward events

    Its task is to properly configure the source/destination of metrics-related
    events, using info in the parameter store.

    Example structure of the parameter store

    Name=/monitors/MonitorName Value=123456789123
    Name=/monitored_projects/ProjectName/CustomTag Value=987654321987

    CustomTag can be used when a project has more than one account (e.g. dev/int/prod)

    Args:
        event (dict): the payload received for this execution
        context: the execution context
    """

    logger.info("Starting invocation with payload:")
    logger.info(json.dumps(event))

    eb_put = event["action"] == "EBPut"

    monitors = ssm_client.get_parameters_by_path(Path="/monitors/", Recursive=True)[
        "Parameters"
    ]
    monitored_projects = ssm_client.get_parameters_by_path(
        Path="/monitored_projects/", Recursive=True
    )["Parameters"]

    monitors = flatten_parameters(monitors)
    monitored_projects = flatten_parameters(monitored_projects)

    # this means we are serving as monitored_project
    for account_id, project_name in monitors.items():

        logger.info(f"Connecting to monitor {project_name} in account {account_id}")

        event_pattern = {
            "source": ["metric_extractor"],
            "detail-type": ["metric_extractor"],
        }

        if eb_put:
            # allow monitor to send us events
            allow_event_puts(account_id)
        else:
            # forward our metrics to monitor
            forward_events(account_id, event_pattern, "MetricValues")

    # this means we are serving as monitor
    for account_id, project_name in monitored_projects.items():

        logger.info(
            f"Connecting to monitored project {project_name} in account {account_id}"
        )

        event_pattern = {
            "source": ["metric_fetch"],
            "detail-type": ["metric_fetch"],
        }

        if eb_put:
            # allow monitored_project to send us events
            allow_event_puts(account_id)
        else:
            # send requests to fetch new data to monitored_projects
            forward_events(account_id, event_pattern, "FetchData")
