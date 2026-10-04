"""Vercel serverless entrypoint. Vercel's Python runtime serves the WSGI `app` object."""

from config.wsgi import application

app = application
