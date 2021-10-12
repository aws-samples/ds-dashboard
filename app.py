#!/usr/bin/env python3
import os

from aws_cdk import core
from ds_dashboard.spoke import SpokeStack

app = core.App()

usecase_stack = SpokeStack(
    app,
    "ds-dashboard-spoke-stack",
)
app.synth()
