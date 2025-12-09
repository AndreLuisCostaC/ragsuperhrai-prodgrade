import os
import zipfile


def main():
    """Create Lambda deployment package with only the required Python files."""
    print("Creating Lambda deployment package...")
    
    # List of Python files to include in the deployment
    python_files = [
        "conversation_history_manager.py",
        "lambda_handler.py",
        "main.py",
        "rag_service.py",
        "schemas.py",
    ]
    
    # Remove existing zip file if it exists
    if os.path.exists("lambda-deployment.zip"):
        os.remove("lambda-deployment.zip")
        print("Removed existing lambda-deployment.zip")
    
    # Create zip file
    print("Creating zip file...")
    files_added = 0
    with zipfile.ZipFile("lambda-deployment.zip", "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in python_files:
            if os.path.exists(file):
                zipf.write(file, file)
                files_added += 1
                print(f"  Added: {file}")
            else:
                print(f"  Warning: {file} not found, skipping")
    
    if files_added == 0:
        print("✗ Error: No files were added to the zip file")
        return
    
    # Show package size
    size_mb = os.path.getsize("lambda-deployment.zip") / (1024 * 1024)
    print(f"✓ Created lambda-deployment.zip ({size_mb:.2f} MB) with {files_added} file(s)")


if __name__ == "__main__":
    main()
