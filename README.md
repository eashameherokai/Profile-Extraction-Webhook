# Profile-Extraction-Webhook
Profile Extraction Webhook

Deployment commands:
docker buildx build --platform linux/amd64 \
  -t us-central1-docker.pkg.dev/ok-ai-otp/okai-backend/profile-extraction:v12 \
  --push . && \
gcloud run deploy profile-extraction-service \
  --image us-central1-docker.pkg.dev/ok-ai-otp/okai-backend/profile-extraction:v12 \
  --region us-central1 \
  --set-env-vars BACKEND_API_URL=https://ok-ai-backend-prod-36igu2sfua-uc.a.run.app/api,JWT_TOKEN=YOUR_ACTUAL_JWT_TOKEN_HERE,AUTOMATE_SERVICE_URL=https://automate-profile-extraction-service-456784797908.us-central1.run.app/webhook
