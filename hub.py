#!/usr/bin/env python3

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os


from aws_cdk import core
from ds_dashboard.hub import HubStack

app = core.App()

management_stack = HubStack(app, "ds-dashboard-hub-stack")
app.synth()


# HUB FOR DASHBOARD / METRICS
