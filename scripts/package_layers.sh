#!/bin/bash
# Package Lambda layers as zip files
# Usage: ./package_layers.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGES_DIR="$PROJECT_ROOT/packages"
DIST_DIR="$PROJECT_ROOT/dist"

mkdir -p "$DIST_DIR"

echo "📦 Creating Lambda layer zip files..."
echo ""

TOTAL_ZIP=0
for i in 1 2 3; do
    LAYER_DIR="$PACKAGES_DIR/layer$i"
    ZIP_FILE="$DIST_DIR/layer$i.zip"
    
    if [ -d "$LAYER_DIR/python" ] && [ "$(ls -A "$LAYER_DIR/python" 2>/dev/null)" ]; then
        cd "$LAYER_DIR"
        rm -f "$ZIP_FILE"
        zip -r -q "$ZIP_FILE" python
        
        UNZIP_SIZE=$(du -sm "$LAYER_DIR" | cut -f1)
        ZIP_SIZE=$(du -sm "$ZIP_FILE" | cut -f1)
        TOTAL_ZIP=$((TOTAL_ZIP + ZIP_SIZE))
        echo "✅ layer$i.zip: ${ZIP_SIZE}MB compressed / ${UNZIP_SIZE}MB uncompressed"
    else
        echo "⏭️  Skipping layer$i (empty)"
    fi
done

echo ""
echo "=================================================="
echo "📁 Output: $DIST_DIR"
echo "   Total compressed: ${TOTAL_ZIP}MB"
echo "=================================================="
ls -lh "$DIST_DIR"/*.zip 2>/dev/null

echo ""
echo "🚀 Deploy commands:"
echo ""
cat << 'EOF'
# Layer 1: boto3 + grpc
aws lambda publish-layer-version \
  --layer-name app-boto3-grpc \
  --zip-file fileb://dist/layer1.zip \
  --compatible-runtimes python3.12

# Layer 2: langchain + openai
aws lambda publish-layer-version \
  --layer-name app-langchain-openai \
  --zip-file fileb://dist/layer2.zip \
  --compatible-runtimes python3.12

# Layer 3: fastapi + chromadb-client
aws lambda publish-layer-version \
  --layer-name app-fastapi-chromadb \
  --zip-file fileb://dist/layer3.zip \
  --compatible-runtimes python3.12
EOF