"""API routes for metrics export."""

import csv
import io
import logging
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.engine import Engine

from sync_airbnb.api.routes._helpers import validate_account_exists, validate_date_range
from sync_airbnb.db.readers import metrics as metrics_readers
from sync_airbnb.dependencies import get_db_engine

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "/accounts/{account_id}/metrics/export",
    summary="Export metrics to CSV or JSON",
    description="""
    Export metrics for an account and date range.

    **Path Parameters:**
    - account_id: The Airbnb account ID (numeric string)

    **Query Parameters:**
    - start_date: Start date (inclusive, format: YYYY-MM-DD)
    - end_date: End date (exclusive, format: YYYY-MM-DD)
    - format: Export format ("csv" or "json", default: "csv")
    - metric_type: Which metrics to export ("chart_query", "list_of_metrics", "chart_summary", "all")

    **Export Formats:**
    - **CSV**: Returns CSV file with headers, suitable for Excel/Google Sheets
    - **JSON**: Returns JSON array of metric objects

    **Use Cases:**
    - Export data for BI tools (Tableau, PowerBI, etc.)
    - Analyze data in Excel or Google Sheets
    - Generate reports
    - Backup data

    **Example:**
    ```bash
    # Export chart_query metrics as CSV
    GET /api/v1/accounts/310316675/metrics/export?start_date=2025-01-01&end_date=2025-02-01&format=csv&metric_type=chart_query

    # Export all metrics as JSON
    GET /api/v1/accounts/310316675/metrics/export?start_date=2025-01-01&end_date=2025-02-01&format=json&metric_type=all
    ```

    **Authentication Required:** API key (future enhancement - P0-1)
    """,
    responses={
        200: {
            "description": "Metrics exported successfully",
            "content": {
                "text/csv": {
                    "example": "time,account_id,listing_id,listing_name,metric_id,home_page_views\\n2025-01-01,310316675,12345,Beach House,abc123,50\\n"
                },
                "application/json": {
                    "example": {
                        "account_id": "310316675",
                        "start_date": "2025-01-01",
                        "end_date": "2025-02-01",
                        "metric_type": "chart_query",
                        "count": 100,
                        "metrics": [
                            {
                                "time": "2025-01-01T00:00:00Z",
                                "account_id": "310316675",
                                "listing_id": "12345",
                                "listing_name": "Beach House",
                                "metric_id": "abc123",
                                "home_page_views": 50,
                                "contact_host_clicks": 5,
                                "visitors_views": 45,
                                "search_appearances": 200,
                            }
                        ],
                    }
                },
            },
        },
        400: {
            "description": "Invalid date range or format",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_REQUEST",
                            "message": "start_date must be before end_date",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
        404: {
            "description": "Account not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "NOT_FOUND",
                            "message": "Account 310316675 not found",
                            "details": {},
                            "request_id": "uuid-here",
                        }
                    }
                }
            },
        },
    },
)
async def export_metrics(
    account_id: str,
    start_date: date = Query(..., description="Start date (inclusive, YYYY-MM-DD)"),
    end_date: date = Query(..., description="End date (exclusive, YYYY-MM-DD)"),
    format: str = Query("csv", regex="^(csv|json)$", description="Export format (csv or json)"),
    metric_type: str = Query(
        "chart_query",
        regex="^(chart_query|list_of_metrics|chart_summary|all)$",
        description="Which metrics to export",
    ),
    engine: Engine = Depends(get_db_engine),
):
    """Export metrics for an account and date range."""
    # Validate account exists
    validate_account_exists(engine, account_id)

    # Validate date range
    validate_date_range(start_date, end_date)

    # Fetch metrics
    if metric_type == "all":
        metrics_data = metrics_readers.get_all_metrics(engine, account_id, start_date, end_date)
        # For "all", flatten into single list with metric_type prefix
        all_metrics = []
        for mt, metrics in metrics_data.items():
            for metric in metrics:
                metric["metric_type"] = mt
                all_metrics.append(metric)
        metrics = all_metrics
    elif metric_type == "chart_query":
        metrics = metrics_readers.get_chart_query_metrics(engine, account_id, start_date, end_date)
    elif metric_type == "list_of_metrics":
        metrics = metrics_readers.get_list_of_metrics_metrics(engine, account_id, start_date, end_date)
    elif metric_type == "chart_summary":
        metrics = metrics_readers.get_chart_summary_metrics(engine, account_id, start_date, end_date)

    # Handle empty results
    if not metrics:
        if format == "json":
            return {
                "account_id": account_id,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "metric_type": metric_type,
                "count": 0,
                "metrics": [],
            }
        else:
            # Return empty CSV with headers
            return StreamingResponse(
                iter(["time,account_id,listing_id,listing_name\n"]),
                media_type="text/csv",
                headers={
                    "Content-Disposition": f'attachment; filename="metrics_{account_id}_{start_date}_{end_date}.csv"'
                },
            )

    # Export as CSV
    if format == "csv":
        # Generate CSV
        output = io.StringIO()
        fieldnames = list(metrics[0].keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        # Convert datetime objects to strings for CSV
        for metric in metrics:
            row = {}
            for key, value in metric.items():
                # Convert datetime to ISO string
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
                else:
                    row[key] = value
            writer.writerow(row)

        # Return as streaming response
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="metrics_{account_id}_{start_date}_{end_date}.csv"'},
        )

    # Export as JSON
    else:
        # Convert datetime objects to strings for JSON
        json_metrics = []
        for metric in metrics:
            row = {}
            for key, value in metric.items():
                if hasattr(value, "isoformat"):
                    row[key] = value.isoformat()
                else:
                    row[key] = value
            json_metrics.append(row)

        return {
            "account_id": account_id,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "metric_type": metric_type,
            "count": len(json_metrics),
            "metrics": json_metrics,
        }
