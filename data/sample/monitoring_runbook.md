# Monitoring service — Fictional demonstration runbook

This synthetic runbook is intended for a software portfolio demonstration only.

## Model monitoring
The monitoring service computes mean absolute error (MAE) daily over the latest 500 labelled predictions. A performance alert is raised when MAE exceeds 0.8 for two consecutive daily windows. This threshold belongs to a fictional regression model and is not the Aster PX100 vibration threshold.

## Data quality
Missing asset_id values are rejected before inference. If a sensor stops sending readings for more than 120 seconds, the dashboard marks that sensor as stale. Staleness is a data-availability signal; it is not proof that the physical machine has failed.

## Incident response
For a stale sensor, first inspect the ingestion service status and the timestamp of the last received measurement. This example contains no production restart command, contact roster, or service-level agreement.
