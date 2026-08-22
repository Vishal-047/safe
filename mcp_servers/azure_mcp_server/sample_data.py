import logging

logger = logging.getLogger('safelane.ingestion')

def get_sample_incidents():
    """Returns a list of realistic sample incident records for demo seeding."""
    return [
        {
            "incident_id": "INC-001",
            "title": "Payment processing failure",
            "description": "Payment gateway integrations started failing with HTTP 500 errors after deployment, causing 25% drop in successful checkouts.",
            "severity": "high",
            "timestamp": "2023-10-15T08:30:00Z",
            "affected_repo": "payment-service"
        },
        {
            "incident_id": "INC-002",
            "title": "Auth middleware crash",
            "description": "Auth middleware crashed when handling malformed JWT tokens due to missing null check, blocking user logins.",
            "severity": "critical",
            "timestamp": "2023-11-02T14:15:00Z",
            "affected_repo": "auth-service"
        },
        {
            "incident_id": "INC-003",
            "title": "Database connection timeout",
            "description": "Connection pool exhaustion led to DB timeouts. The pool limit was improperly configured to 10 in the recent PR.",
            "severity": "medium",
            "timestamp": "2024-01-20T09:45:00Z",
            "affected_repo": "inventory-api"
        },
        {
            "incident_id": "INC-004",
            "title": "API rate limiting incident",
            "description": "Missing rate limit headers from the new reverse proxy config triggered an unhandled exception in the client SDKs.",
            "severity": "low",
            "timestamp": "2024-02-10T11:20:00Z",
            "affected_repo": "api-gateway"
        },
        {
            "incident_id": "INC-005",
            "title": "Deployment rollback due to missing env var",
            "description": "Application failed to start in production because the newly introduced REQUIRED_SECRET env variable was not provisioned.",
            "severity": "high",
            "timestamp": "2024-03-05T16:00:00Z",
            "affected_repo": "user-profile-service"
        }
    ]

def upload_sample_data(endpoint: str, key: str, index_name: str):
    """Upload sample incident data to Azure AI Search index."""
    try:
        from azure.core.credentials import AzureKeyCredential
        from azure.search.documents import SearchClient
        
        credential = AzureKeyCredential(key)
        client = SearchClient(endpoint=endpoint, index_name=index_name, credential=credential)
        
        incidents = get_sample_incidents()
        
        logger.info(f"Uploading {len(incidents)} sample incidents to index '{index_name}'...")
        result = client.upload_documents(documents=incidents)
        logger.info("Upload complete.")
        return result
    except Exception as e:
        logger.error(f"Failed to upload sample data: {e}")
        return None
