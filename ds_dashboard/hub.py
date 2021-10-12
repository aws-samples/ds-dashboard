# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    core,
    aws_dynamodb,
    aws_lambda,
    aws_iam,
    aws_events,
    aws_events_targets,
)


class HubStack(core.Stack):
    """
    This class deploys the resources needed to operate the Hub of this solution.
    The list of resources created is:

    * A DDB table, a lambda to write new items into it, and an EventBridge rule to trigger the lambda
    * a lambda to setup the connection to al new spoke
    * a lambda to request new data from all the spokes
    """

    def __init__(self, scope: core.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = aws_dynamodb.Table(
            self,
            id="ds-dashboard-hub-table",
            table_name="ds-dashboard-hub-table",
            partition_key=aws_dynamodb.Attribute(
                name="MetricName", type=aws_dynamodb.AttributeType.STRING
            ),
            sort_key=aws_dynamodb.Attribute(
                name="ExtractionDate", type=aws_dynamodb.AttributeType.STRING
            ),
            point_in_time_recovery=True,
            removal_policy=core.RemovalPolicy.DESTROY,
        )

        # This lambda is triggered by events arriving from the spoke accounts and writes to ddb
        dynamo_write_lambda = aws_lambda.Function(
            self,
            "ds-dashboard-dynamo-write",
            function_name="ds-dashboard-dynamo-write",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.asset("lambda_function_code"),
            handler="dynamo_write.lambda_handler",
            timeout=core.Duration.minutes(1),
            memory_size=128,
            environment={"DDB_TABLE_NAME": table.table_name},
        )

        dynamo_rule = aws_events.Rule(
            self,
            id="eb_to_ddb_rule",
            rule_name="eb_to_ddb_rule",
            description="eb_to_ddb_rule",
            enabled=True,
            event_pattern=aws_events.EventPattern(
                source=["metric_extractor"],
                detail_type=["metric_extractor"],
            ),
        )

        dynamo_rule.apply_removal_policy(core.RemovalPolicy.DESTROY)

        dynamo_rule.add_target(aws_events_targets.LambdaFunction(dynamo_write_lambda))

        dynamo_write_lambda.add_permission(
            "fromEB",
            principal=aws_iam.ServicePrincipal("events.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=dynamo_rule.rule_arn,
        )

        table.grant_write_data(dynamo_write_lambda)

        # this lambda configures the connection to the spokes.
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

        # a third lambda, just a utility function to emit a custom event. the event will be forwarded to all spokes and will trigger there new extractions

        fetch_new_data = aws_lambda.Function(
            self,
            "ds-dashboard-fetch-new-data",
            function_name="ds-dashboard-fetch-new-data",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.asset("lambda_function_code"),
            handler="fetch_metric_values.lambda_handler",
            timeout=core.Duration.minutes(1),
            memory_size=128,
        )

        fetch_policy_statement = aws_iam.PolicyStatement(
            actions=["events:PutEvents"], resources=["*"]
        )

        fetch_new_data.role.add_to_policy(fetch_policy_statement)
