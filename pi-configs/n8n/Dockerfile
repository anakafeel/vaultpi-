# Base pinned to 1.106.3, NOT :latest - n8n:latest (2.37.10, pulled
# 2026-09-07) crashes with SIGBUS on this Pi (arm64) within seconds of
# every startup, even against a completely empty data volume (isolated by
# testing a scratch container) - an upstream ARM64 regression, not
# anything specific to this deployment. 1.106.3 was bisected as the last
# version confirmed to start cleanly. Revisit once a newer release is
# confirmed fixed.
#
# n8n's Execute Command node runs inside this container, not on the Pi
# host - it has no python3 and no access to ~/vaultpi by default. This adds
# just enough to run the existing photo-search scripts (boto3, numpy) via
# Alpine's own prebuilt apk packages, so nothing needs compiling on-device.
FROM n8nio/n8n:1.106.3

USER root
RUN apk add --no-cache python3 py3-boto3 py3-numpy
USER node
