#!/bin/bash
# Build optimized Lambda layers using uv package manager
# Usage: ./build_layers.sh
#
# Creates 3 Lambda layers optimized for size (<45MB each)
# Uses chromadb-client for HTTP client mode (requires external ChromaDB server)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
PACKAGES_DIR="$PROJECT_ROOT/packages"
PYTHON_VERSION="3.12"

# Optimization function - strips unnecessary files
optimize_layer() {
    local LAYER_DIR=$1
    echo "  → Optimizing..."
    
    # Remove __pycache__ and .pyc files
    find "$LAYER_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
    
    # Clean dist-info (keep only essential metadata)
    find "$LAYER_DIR" -type d -name "*.dist-info" -exec sh -c '
        for dir; do
            find "$dir" -type f ! -name "METADATA" ! -name "RECORD" ! -name "WHEEL" ! -name "entry_points.txt" -delete 2>/dev/null || true
        done
    ' _ {} + 2>/dev/null || true
    
    # Remove tests and documentation (BUT keep botocore/docs and boto3/docs which are required)
    find "$LAYER_DIR" -type d \( -name "tests" -o -name "test" -o -name "testing" -o -name "examples" \) -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR" -type d -name "docs" ! -path "*/botocore/docs*" ! -path "*/boto3/docs*" -exec rm -rf {} + 2>/dev/null || true
    find "$LAYER_DIR" -type d -name "doc" ! -path "*/botocore/*" ! -path "*/boto3/*" -exec rm -rf {} + 2>/dev/null || true
    
    # Remove unnecessary file types
    find "$LAYER_DIR" -type f \( -name "*.md" -o -name "*.rst" -o -name "LICENSE*" -o -name "CHANGELOG*" -o -name "*.pyi" \) -delete 2>/dev/null || true
    find "$LAYER_DIR" -type f -name "*.txt" ! -name "requirements*.txt" ! -name "entry_points.txt" -delete 2>/dev/null || true
    
    # Strip shared libraries
    if command -v strip &> /dev/null; then
        find "$LAYER_DIR" -type f -name "*.so*" -exec strip --strip-unneeded {} + 2>/dev/null || true
    fi
    
    # Package-specific cleanup (preserve numpy)
    rm -rf "$LAYER_DIR/python/numpy/tests" "$LAYER_DIR/python/numpy/f2py" 2>/dev/null || true
}

# Remove duplicate packages from target layer
remove_duplicates() {
    local TARGET=$1
    shift
    for SOURCE in "$@"; do
        if [ -d "$SOURCE/python" ]; then
            for pkg in $(ls "$SOURCE/python/" 2>/dev/null); do
                rm -rf "$TARGET/python/$pkg" 2>/dev/null || true
            done
        fi
    done
}

echo "🚀 Building Lambda Layers with uv"
echo "=================================="
echo "Using chromadb-client (HTTP client mode)"
echo ""

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf "$PACKAGES_DIR/layer1" "$PACKAGES_DIR/layer2" "$PACKAGES_DIR/layer3"
mkdir -p "$PACKAGES_DIR/layer1/python" "$PACKAGES_DIR/layer2/python" "$PACKAGES_DIR/layer3/python"

# ============================================================
# LAYER 1: AWS SDK (boto3) + grpc
# ============================================================
echo ""
echo "📦 Layer 1: boto3 + grpc"
uv pip install \
    "boto3>=1.41.4" \
    "grpcio>=1.60.0" \
    --target "$PACKAGES_DIR/layer1/python" \
    --python-version "$PYTHON_VERSION" \
    --quiet

optimize_layer "$PACKAGES_DIR/layer1"
LAYER1_SIZE=$(du -sm "$PACKAGES_DIR/layer1" | cut -f1)
echo "   Size: ${LAYER1_SIZE}MB"

# ============================================================
# LAYER 2: LangChain (core packages only)
# ============================================================
echo ""
echo "📦 Layer 2: LangChain"
uv pip install \
    "langchain[core]>=1.1.0" \
    "langchain-aws>=0.1.0" \
    "langchain-chroma>=1.0.0" \
    --target "$PACKAGES_DIR/layer2/python" \
    --python-version "$PYTHON_VERSION" \
    --quiet

# Remove heavy chromadb dependencies (numpy will be in layer 3)
rm -rf "$PACKAGES_DIR/layer2/python/chromadb" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/chromadb_rust_bindings" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/onnxruntime" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/numpy" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/numpy.libs" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/sympy" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/mpmath" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/tokenizers" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/huggingface_hub" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/hf_xet" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/kubernetes" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/grpc" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/grpcio"* 2>/dev/null || true
# Move these to layer 3
rm -rf "$PACKAGES_DIR/layer2/python/pydantic" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/pydantic_core" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/pydantic"* 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/uvloop" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/uvloop"* 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/pygments" 2>/dev/null || true
rm -rf "$PACKAGES_DIR/layer2/python/pygments"* 2>/dev/null || true

remove_duplicates "$PACKAGES_DIR/layer2" "$PACKAGES_DIR/layer1"
optimize_layer "$PACKAGES_DIR/layer2"
LAYER2_SIZE=$(du -sm "$PACKAGES_DIR/layer2" | cut -f1)
echo "   Size: ${LAYER2_SIZE}MB"

# ============================================================
# LAYER 3: FastAPI + chromadb-client + pydantic + numpy
# ============================================================
echo ""
echo "📦 Layer 3: FastAPI + chromadb-client + pydantic + numpy"
uv pip install \
    "fastapi>=0.122.0" \
    "mangum>=0.19.0" \
    "python-dotenv>=1.2.1" \
    "python-multipart>=0.0.20" \
    "uvicorn>=0.38.0" \
    "chromadb-client>=1.0.0" \
    "pydantic>=2.0.0" \
    "pygments>=2.0.0" \
    "numpy>=1.26.0" \
    --target "$PACKAGES_DIR/layer3/python" \
    --python-version "$PYTHON_VERSION" \
    --quiet

# NOTE: Keep numpy - it's required by langchain-chroma in layer 2
# Lambda merges all layers, so numpy in layer 3 will be available to layer 2

remove_duplicates "$PACKAGES_DIR/layer3" "$PACKAGES_DIR/layer1" "$PACKAGES_DIR/layer2"
optimize_layer "$PACKAGES_DIR/layer3"
LAYER3_SIZE=$(du -sm "$PACKAGES_DIR/layer3" | cut -f1)
echo "   Size: ${LAYER3_SIZE}MB"

# ============================================================
# Summary
# ============================================================
TOTAL=$((LAYER1_SIZE + LAYER2_SIZE + LAYER3_SIZE))

echo ""
echo "=================================================="
echo "📊 Build Summary"
echo "=================================================="
printf "  Layer 1 (boto3+grpc):       %3sMB" "$LAYER1_SIZE"
[ "$LAYER1_SIZE" -le 50 ] && echo " ✅" || echo " ⚠️"
printf "  Layer 2 (langchain+openai): %3sMB" "$LAYER2_SIZE"
[ "$LAYER2_SIZE" -le 50 ] && echo " ✅" || echo " ⚠️"
printf "  Layer 3 (fastapi+numpy):    %3sMB" "$LAYER3_SIZE"
[ "$LAYER3_SIZE" -le 70 ] && echo " ✅" || echo " ⚠️"
echo "--------------------------------------------------"
echo "  Total:                      ${TOTAL}MB"
echo ""

# Check total Lambda limit (250MB unzipped)
if [ "$TOTAL" -gt 250 ]; then
    echo "⚠️  Total exceeds Lambda 250MB limit!"
else
    echo "✅ Total within Lambda 250MB limit"
fi

echo ""
echo "📝 Required environment variables for your Lambda:"
echo "   CHROMADB_HOST - ChromaDB server hostname"
echo "   CHROMADB_PORT - ChromaDB server port (default: 8000)"
echo "   OPENAI_API_KEY - OpenAI API key"
echo ""
echo "Next: Run './scripts/package_layers.sh' to create zip files"