#!/usr/bin/env bash
# Run in the owner's Google Cloud Shell, not Kaggle. No keys are embedded.
# Creates a NEW private bucket, then tests CRUD on one sandbox object only.
set -euo pipefail
PROJECT_ID="${PROJECT_ID:-locdeproject}"
REGION="${REGION:-us-central1}"
: "${BUCKET_NAME:?Set BUCKET_NAME to a new globally unique bucket name}"
command -v gcloud >/dev/null
command -v python3 >/dev/null
gcloud projects describe "$PROJECT_ID" --format='value(projectId)'
gcloud storage buckets create "gs://$BUCKET_NAME" \
  --project="$PROJECT_ID" --location="$REGION" --default-storage-class=STANDARD \
  --uniform-bucket-level-access --public-access-prevention
# Use the bucket's default recovery policy initially; inspect costs/policy.
gcloud storage buckets describe "gs://$BUCKET_NAME"
GCS_TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$GCS_TEST_DIR"' EXIT
GCS_TEST_KEY="sandbox/onboarding-$(date -u +%Y%m%dT%H%M%S)-$RANDOM/probe.txt"
printf 'GCS onboarding create\n' > "$GCS_TEST_DIR/probe.txt"
gcloud storage cp "$GCS_TEST_DIR/probe.txt" "gs://$BUCKET_NAME/$GCS_TEST_KEY" --if-generation-match=0
gcloud storage cp "gs://$BUCKET_NAME/$GCS_TEST_KEY" "$GCS_TEST_DIR/read.txt"
cmp "$GCS_TEST_DIR/probe.txt" "$GCS_TEST_DIR/read.txt"
GCS_TEST_GENERATION="$(gcloud storage objects describe "gs://$BUCKET_NAME/$GCS_TEST_KEY" --format='value(generation)')"
printf 'GCS onboarding update\n' > "$GCS_TEST_DIR/probe.txt"
gcloud storage cp "$GCS_TEST_DIR/probe.txt" "gs://$BUCKET_NAME/$GCS_TEST_KEY" --if-generation-match="$GCS_TEST_GENERATION"
gcloud storage cp "gs://$BUCKET_NAME/$GCS_TEST_KEY" "$GCS_TEST_DIR/updated.txt"
cmp "$GCS_TEST_DIR/probe.txt" "$GCS_TEST_DIR/updated.txt"
GCS_TEST_GENERATION="$(gcloud storage objects describe "gs://$BUCKET_NAME/$GCS_TEST_KEY" --format='value(generation)')"
gcloud storage rm "gs://$BUCKET_NAME/$GCS_TEST_KEY" --if-generation-match="$GCS_TEST_GENERATION"
python3 - "$BUCKET_NAME" "$GCS_TEST_KEY" <<'PY'
import subprocess,sys
# Distinguish a missing object from an authentication/permission failure.
r=subprocess.run(['gcloud','storage','objects','describe',
    'gs://'+sys.argv[1]+'/'+sys.argv[2]],capture_output=True,text=True)
if r.returncode==0:raise RuntimeError('Deleted test object still exists')
message=r.stderr.lower()
if any(word in message for word in ['403','permission','unauthenticated','forbidden']):
    raise RuntimeError('Cannot verify deletion: authorization failure')
if not any(word in message for word in ['404','not found','does not exist']):
    raise RuntimeError('Cannot verify deletion: inspect Cloud Shell diagnostics')
PY
printf 'Sandbox CRUD completed as Cloud Shell identity. Kaggle IAM/download not yet verified.\n'
