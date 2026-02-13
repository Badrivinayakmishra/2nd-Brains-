#!/bin/bash
# Load environment variables from .env file
source .env 2>/dev/null || true

export USE_AZURE_OPENAI=true
export AZURE_OPENAI_ENDPOINT="${AZURE_OPENAI_ENDPOINT:-https://secondbrain-resource.openai.azure.com/}"
# AZURE_OPENAI_API_KEY should be set in .env file
export AZURE_CHAT_DEPLOYMENT="${AZURE_CHAT_DEPLOYMENT:-gpt-4.1}"

echo "Starting with Azure OpenAI..."
echo "USE_AZURE_OPENAI=$USE_AZURE_OPENAI"
echo "AZURE_CHAT_DEPLOYMENT=$AZURE_CHAT_DEPLOYMENT"

./venv_new/bin/python app_v2.py
