import json
import logging
import os
import traceback

# Configure logging for Lambda first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize handler at module load time
_handler = None

try:
    logger.info("Initializing Lambda handler at module load...")
    from mangum import Mangum
    from main import app
    
    # Create a Mangum handler for the FastAPI app
    # Set lifespan to "off" to avoid async lifespan issues in Lambda
    _handler = Mangum(app, lifespan="off")
    
    logger.info("✓ Lambda handler initialized successfully")
    logger.info(f"Environment check - AWS_REGION: {bool(os.getenv('DEFAULT_AWS_REGION'))}, BEDROCK_MODEL_ID: {bool(os.getenv('BEDROCK_MODEL_ID'))}, CHROMA_API_KEY: {bool(os.getenv('CHROMA_API_KEY'))}")
except Exception as e:
    error_msg = f"✗ Failed to initialize Lambda handler: {str(e)}\n{traceback.format_exc()}"
    logger.error(error_msg)
    # Set handler to None so we can handle it in the wrapper
    _handler = None


def handler(event, context):
    """
    Lambda handler function that wraps the Mangum handler with error handling.
    
    This function:
    1. Catches any runtime errors and returns a proper error response
    2. Logs all errors to CloudWatch for debugging
    3. Provides detailed logging for troubleshooting
    """
    try:
        # Log invocation details
        if isinstance(event, dict):
            http_method = event.get("httpMethod", event.get("requestContext", {}).get("http", {}).get("method", "UNKNOWN"))
            path = event.get("path", event.get("rawPath", "UNKNOWN"))
            logger.info(f"Lambda invoked: {http_method} {path}")
        else:
            logger.info(f"Lambda invoked with event type: {type(event)}")
        
        # Check if handler was initialized
        if _handler is None:
            error_msg = "Handler was not initialized. Check CloudWatch logs for initialization errors."
            logger.error(error_msg)
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json",
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "*",
                    "Access-Control-Allow-Headers": "*",
                },
                "body": json.dumps({
                    "error": "Internal server error",
                    "detail": error_msg
                })
            }
        
        # Call the Mangum handler (it handles async internally)
        logger.debug("Calling Mangum handler...")
        result = _handler(event, context)
        
        # Log successful completion
        if isinstance(result, dict):
            status_code = result.get("statusCode", "unknown")
            logger.info(f"Handler completed with status: {status_code}")
        else:
            logger.warning(f"Handler returned unexpected type: {type(result)}")
        
        return result
        
    except Exception as e:
        # Catch any runtime errors and return a proper error response
        error_detail = f"Runtime error in Lambda handler: {str(e)}\n{traceback.format_exc()}"
        logger.error(error_detail)
        
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "*",
                "Access-Control-Allow-Headers": "*",
            },
            "body": json.dumps({
                "error": "Internal server error",
                "detail": "An error occurred processing the request. Check CloudWatch logs for details.",
                "message": str(e)
            })
        }