# Workshop telemetry API — Fictional interface specification

This is a synthetic example for evaluating document retrieval. No live endpoint is provided.

## Submitting a measurement
Submit telemetry measurements with POST /api/v1/telemetry. The required JSON fields are asset_id, timestamp, and vibration_rms. The timestamp must use UTC ISO 8601. Requests contain one measurement each. A successful submission returns HTTP 202.

## Request validation
The telemetry API rejects a request missing a required field with HTTP 400. The vibration_rms value must be a non-negative number. The API example does not describe authentication, administrator credentials, request-rate limits, or bulk upload.

## Storage
Telemetry measurements are retained for 30 days. The retention period applies to raw measurements, not to maintenance tickets. This demonstration specifies no backup retention period.
