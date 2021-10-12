# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import datetime
import boto3
import json

events_client = boto3.client("events")
sagemaker_client = boto3.client("sagemaker")
ssm_client = boto3.client("ssm")


class Metric:

    _iam_permissions = [
        {
            "Action": ["events:PutEvents"],
            "Resource": "arn:aws:events:**REGION**:**ACCOUNT_ID**:event-bus/default",
        }
    ]

    def __init__(self, metric_name, project_name, metadata, environment):
        """Class constructor. child classes should not need to implement this.

        Args:
            metric_name (str): the name of this metric
            project_name (str): the project the metric belongs to
            metadata (dict): the metadata
        """
        self.metric_name = metric_name
        self.project_name = project_name
        self.metadata = metadata
        self.environment = environment

    def get_iam_permissions(self, region, account_id):

        replaced_list = []
        for p in self._iam_permissions:
            p = (
                str(p)
                .replace("**REGION**", region)
                .replace("**ACCOUNT_ID**", account_id)
            )

            replaced_list.append(eval(p))
        return replaced_list

    def extract(self):
        """The method that calculates the value of the metric and formats the output. child classes should not need to implement this."""
        return {
            "MetricName": self.metric_name,
            "MetricValue": self._compute_value(),
            "ExtractionDate": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
            "Metadata": self.metadata,
            "Environment": self.environment,
            "ProjectName": self.project_name,
        }

    def emit_event(self, payload):
        """emit an event with a given payload. child classes should not need to implement this.

        Args:
            payload (dict): the payload of the event to be emitted
        """

        response = events_client.put_events(
            Entries=[
                {
                    "Source": "metric_extractor",
                    "Resources": [],
                    "DetailType": "metric_extractor",
                    "Detail": json.dumps(payload),
                }
            ]
        )

    def _compute_value(self):
        """This is where the actual calculation happens. Child classes MUST implement this"""
        raise NotImplementedError


class TotalCompletedTrainingJobs(Metric):

    _iam_permissions = Metric._iam_permissions + [
        {"Action": ["sagemaker:ListTrainingJobs"], "Resource": "*"}
    ]

    def _compute_value(self):

        jobs = sagemaker_client.list_training_jobs(
            StatusEquals="Completed",
        )["TrainingJobSummaries"]

        return len(jobs)


class CompletedTrainingJobs24h(Metric):

    _iam_permissions = Metric._iam_permissions + [
        {"Action": ["sagemaker:ListTrainingJobs"], "Resource": "*"}
    ]

    def _compute_value(self):

        today = datetime.datetime.now()
        yesterday = today - datetime.timedelta(days=1)

        jobs = sagemaker_client.list_training_jobs(
            StatusEquals="Completed",
            LastModifiedTimeAfter=yesterday,
            LastModifiedTimeBefore=today,
        )["TrainingJobSummaries"]

        return len(jobs)


class NumberEndPointsInService(Metric):

    _iam_permissions = Metric._iam_permissions + [
        {"Action": "sagemaker:ListEndpoints", "Resource": "*"}
    ]

    def _compute_value(self):

        eps = sagemaker_client.list_endpoints(
            StatusEquals="InService",
        )["Endpoints"]

        return len(eps)


class SSMParamStoreValueMyName(Metric):
    _iam_permissions = Metric._iam_permissions + [
        {
            "Action": "ssm:GetParameter",
            "Resource": "arn:aws:ssm:*:**ACCOUNT_ID**:parameter/MyName",
        }
    ]

    def _compute_value(self):

        return ssm_client.get_parameter(Name="MyName")["Parameter"]["Value"]
