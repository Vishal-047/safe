import logging
import azure.functions as func

app = func.FunctionApp()

logger = logging.getLogger('safelane.ingestion')
logger.setLevel(logging.INFO)

@app.timer_trigger(schedule="0 0 */6 * * *", arg_name="timer", run_on_startup=False)
async def ingest_recent_incidents(timer: func.TimerRequest) -> None:
    """Query Log Analytics for alerts in the last 6 hours and index them."""
    if timer.past_due:
        logger.info('The timer is past due!')

    logger.info('Timer trigger function executed.')
    # 1. Get all active registrations from the DB
    # 2. For each registration with Azure workspace config:
    #    a. Query Log Analytics for recent alerts/incidents
    #    b. Transform into incident documents
    #    c. Upload to the per-repo Azure AI Search index
    pass

@app.event_grid_trigger(arg_name="event")
async def handle_alert_event(event: func.EventGridEvent) -> None:
    """Process a real-time Azure Monitor alert."""
    logger.info('Event grid trigger processed an event: %s', event.subject)
    # Parse the alert, identify the affected repo, index the incident
    pass

@app.route(route="backfill", auth_level=func.AuthLevel.FUNCTION)
async def backfill_incidents(req: func.HttpRequest) -> func.HttpResponse:
    """Manual seeding of incident data."""
    logger.info('HTTP trigger function processed a request.')
    # Accept a JSON array of incident records and index them
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
             "Invalid JSON payload.",
             status_code=400
        )
        
    return func.HttpResponse(
        "Incidents backfilled successfully.",
        status_code=200
    )
