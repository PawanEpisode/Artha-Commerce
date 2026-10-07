#!/bin/sh
# Container entrypoint (PID 1 is tini). Starts clamd when MEDIA_SCANNER=clamd, waits until it answers, then hands over to the
# command (default: python manage.py run_worker). clamd keeps running as a child of tini; if it dies the HEALTHCHECK fails and the
# host restarts the container.
set -eu

if [ "${MEDIA_SCANNER:-null}" = "clamd" ]; then
  export CLAMD_SOCKET="${CLAMD_SOCKET:-/tmp/clamd.sock}"
  if ! ls /var/lib/clamav/*.cvd /var/lib/clamav/*.cld >/dev/null 2>&1; then
    echo "entrypoint: no ClamAV signatures, running freshclam"
    freshclam --config-file=/app/worker/freshclam.conf --quiet
  fi
  clamd --config-file=/app/worker/clamd.conf &
  # signature updates in the background, twelve checks a day
  freshclam --config-file=/app/worker/freshclam.conf -d &
  echo "entrypoint: waiting for clamd (loading signatures needs about 1 GB of RAM and 20 to 90 seconds)"
  tries=0
  until clamdscan --config-file=/app/worker/clamd.conf --ping 1 >/dev/null 2>&1; do
    tries=$((tries + 1))
    if [ "$tries" -ge 150 ]; then
      echo "entrypoint: clamd did not become ready in time" >&2
      exit 1
    fi
    sleep 2
  done
  echo "entrypoint: clamd is ready"
fi

exec "$@"
