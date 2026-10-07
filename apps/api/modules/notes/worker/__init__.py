"""
PDF worker libraries for F-03 Smart Notes (ERD 6.5): inspect, extract text, OCR, flattened export.

Pure and database-free on purpose: every function takes file paths and plain values and returns frozen dataclasses, so the
job handlers (which own the database and storage glue) stay thin and these can be tested with generated fixtures.
Only the worker image installs their dependencies (`apps/api/worker/requirements-worker.txt`); the API process never
imports this package. PyMuPDF is excluded on purpose (AGPL).
"""
