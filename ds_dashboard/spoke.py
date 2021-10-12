# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from lambda_function_code.metric import *
from aws_cdk import core, aws_iam, aws_lambda, aws_events, aws_events_targets
from aws_cdk.core import Aws, Environment, RemovalPolicy
from botocore.utils import merge_dicts
import json
import os
import logging

logging.basicConfig()

logger = logging.getLogger("stack:spoke")
logger.setLevel(os.getenv("LOGLEVEL", "INFO"))


class SpokeStack(core.Stack):
    """
    This class deploys the resources needed to operate a spoke of this solution
    It receives from the context:

    * a list of metrics whose extraction needs to be deployed in this account
    * the environment of this account. This is a freetext field (no blanks) that is used
    to identify multiple accounts belonging to the same project
    * the name of the project

    For each metric specified in the context, the stack will retrieve from the python code the AIM permissions it needs
    and add them to a new IAM policy

    This policy will be attached to the execution role of the extraction lambda (created also here), which takes care
    of collecting metrics from the local account and writing their values in custom EventBridge events

    The Lambda will be triggered by an EventBridge rule created here. The Hub account will emit a matching event to request a new extraction.

    An additional lambda is in charge of setting up the connection to a new Hub.

    """

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        metrics = self.node.try_get_context("metrics")
        environment = self.node.try_get_context("environment")
        project_name = self.node.try_get_context("project_name")

        if metrics is not None and environment is not None and project_name is not None:

            metrics_parsed = metrics.split(",")
            logger.info(f"Will deploy with the following metrics: {metrics_parsed}")

            iam_list = []
            for m in metrics_parsed:
                class_m = eval(m)

                # create a dummy instance, to retrieve its IAM permissions
                instance_m = class_m("", "", "", "")
                iam_m = instance_m.get_iam_permissions(Aws.REGION, Aws.ACCOUNT_ID)
                iam_list = iam_list + iam_m

            policy_document = {"Version": "2012-10-17", "Statement": iam_list}

            logger.debug("Policy for lambda execution role")
            logger.debug(policy_document)

            doc = aws_iam.PolicyDocument.from_json(policy_document)

            pol = aws_iam.Policy(self, "metric-lambda", document=doc)

            # define a lambda, trigger it from a rule
            metric_lambda = aws_lambda.Function(
                self,
                "ds-dashboard-metric-extraction",
                function_name="ds-dashboard-metric-extraction",
                runtime=aws_lambda.Runtime.PYTHON_3_9,
                code=aws_lambda.Code.asset("lambda_function_code"),
                handler="retrieve_values.lambda_handler",
                timeout=core.Duration.minutes(1),
                memory_size=128,
                environment={
                    "METRIC_NAMES": metrics,
                    "PROJECT_NAME": str(project_name),
                    "ENVIRONMENT": str(environment),
                },
            )

            metric_lambda.role.attach_inline_policy(pol)

            fetch_rule = aws_events.Rule(
                self,
                id="fetch-request-from-hub",
                rule_name="fetch-request-from-hub",
                description="fetch-request-from-hub",
                enabled=True,
                event_pattern=aws_events.EventPattern(
                    source=["metric_fetch"], detail_type=["metric_fetch"]
                ),
            )

            metric_lambda.add_permission(
                "fromEB",
                principal=aws_iam.ServicePrincipal("events.amazonaws.com"),
                action="lambda:InvokeFunction",
                source_arn=fetch_rule.rule_arn,
            )

            fetch_rule.add_target(aws_events_targets.LambdaFunction(metric_lambda))

            # a second lambda to configure event bus operation
            dashboard_connection_lambda = aws_lambda.Function(
                self,
                "ds-dashboard-connection",
                function_name="ds-dashboard-connection",
                runtime=aws_lambda.Runtime.PYTHON_3_9,
                code=aws_lambda.Code.asset("lambda_function_code"),
                handler="dashboard_connection.lambda_handler",
                timeout=core.Duration.minutes(1),
                memory_size=128,
            )

            eb_policy_statement = aws_iam.PolicyStatement(
                actions=[
                    "events:PutRule",
                    "events:PutTargets",
                    "events:PutPermission",
                    "ssm:GetParametersByPath",
                ],
                resources=["*"],
            )

            dashboard_connection_lambda.role.add_to_policy(eb_policy_statement)
        else:
            logger.error(
                "No context for the variables present - please add these with -c in the cdk command."
            )
