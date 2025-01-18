#!/bin/bash

EVENTARC_NAME=$1

DEAD_LETTER_TOPIC=tech-curator-dead-letter

# プロジェクト番号を取得
PROJECT_NUMBER=$(gcloud projects describe $GOOGLE_CLOUD_PROJECT --format="value(projectNumber)")

# サブスクリプション名を取得
SUBSCRIPTION=$(gcloud pubsub subscriptions list --format json | jq -r '.[].name' | grep $EVENTARC_NAME)

# サブスクリプションにIAMポリシーを追加
gcloud pubsub subscriptions add-iam-policy-binding $SUBSCRIPTION \
  --member="serviceAccount:service-$PROJECT_NUMBER@gcp-sa-pubsub.iam.gserviceaccount.com" \
  --role="roles/pubsub.subscriber"

# サブスクリプション設定を更新
gcloud pubsub subscriptions update $SUBSCRIPTION \
  --ack-deadline 600 \
  --dead-letter-topic $DEAD_LETTER_TOPIC \
  --min-retry-delay 300 \
  --max-retry-delay 600