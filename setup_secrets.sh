#!/bin/bash

# Setup Google Cloud Secret Manager secrets from .env file
# This script reads your local .env file and creates secrets in GCP Secret Manager

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Setting up GCP Secret Manager${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found${NC}"
    echo "Please create a .env file with your API credentials"
    exit 1
fi

# Load .env file
set -a
source .env
set +a

# Check if PROJECT_ID is set
if [ -z "$GCP_PROJECT_ID" ]; then
    read -p "Enter your GCP Project ID: " GCP_PROJECT_ID
    export GCP_PROJECT_ID
fi

echo -e "${YELLOW}Project ID: $GCP_PROJECT_ID${NC}"
echo

# Function to create or update secret
create_or_update_secret() {
    local secret_name=$1
    local secret_value=$2

    if [ -z "$secret_value" ]; then
        echo -e "${YELLOW}⚠ Skipping $secret_name (no value provided)${NC}"
        return
    fi

    # Check if secret exists
    if gcloud secrets describe $secret_name --project=$GCP_PROJECT_ID >/dev/null 2>&1; then
        # Update existing secret
        echo "Updating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets versions add $secret_name --data-file=- --project=$GCP_PROJECT_ID
    else
        # Create new secret
        echo "Creating secret: $secret_name"
        echo -n "$secret_value" | gcloud secrets create $secret_name --data-file=- --project=$GCP_PROJECT_ID
    fi

    echo -e "${GREEN}✓ $secret_name${NC}"
}

# Create secrets
echo "Creating/updating secrets..."
echo

create_or_update_secret "SEC_USER_AGENT" "$SEC_USER_AGENT"
create_or_update_secret "REDDIT_CLIENT_ID" "$REDDIT_CLIENT_ID"
create_or_update_secret "REDDIT_CLIENT_SECRET" "$REDDIT_CLIENT_SECRET"
create_or_update_secret "REDDIT_USER_AGENT" "$REDDIT_USER_AGENT"
create_or_update_secret "X_BEARER_TOKEN" "$X_BEARER_TOKEN"

# Optional: Neo4j credentials (if you want to use Neo4j in cloud)
if [ -n "$NEO4J_URI" ]; then
    read -p "Do you want to store Neo4j credentials? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        create_or_update_secret "NEO4J_URI" "$NEO4J_URI"
        create_or_update_secret "NEO4J_USERNAME" "$NEO4J_USERNAME"
        create_or_update_secret "NEO4J_PASSWORD" "$NEO4J_PASSWORD"
        create_or_update_secret "NEO4J_DATABASE" "$NEO4J_DATABASE"
    fi
fi

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Secrets setup complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo "Next step: Grant Cloud Run service account access to secrets"
echo
echo "Run the following command after deploying Cloud Run:"
echo
echo "gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \\"
echo "  --member=\"serviceAccount:[SERVICE_ACCOUNT_EMAIL]\" \\"
echo "  --role=\"roles/secretmanager.secretAccessor\""
echo
