from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import reduce
from typing import List, Dict, Union, Optional, Literal
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson.codec_options import CodecOptions
import calendar

# Initialize FastAPI
app = FastAPI()

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Constants
TZ = ZoneInfo("Asia/Kolkata")
MONGODB_URI = "mongodb+srv://dbadmin:WgF8i17BVrhMveS@hfcl-genai-cosmon-cin-001-uat.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
SESSION_STORE = "sessions"

# Modified Pydantic models with Literal type for frequency
class MetricValue(BaseModel):
    period: str
    value: Union[int, float]

class MetricsResponse(BaseModel):
    metric: str
    values: List[MetricValue]
    remarks: str

class DateRange(BaseModel):
    start_date: str
    end_date: str
    frequency: Literal["Weekly", "Monthly", "Quarterly", "Yearly"]

# MongoDB Connection Class
class MongoDBConnection:
    def __init__(self, db_name: str):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[db_name].with_options(
            codec_options=CodecOptions(tz_aware=True, tzinfo=TZ)
        )

def get_next_monday(date: datetime) -> datetime:
    """Get the next Monday from a given date"""
    days_ahead = (7 - date.isoweekday()) % 7  
    return date + timedelta(days=days_ahead + (1 if days_ahead == 0 else 0))

def get_date_ranges(start_date: datetime, end_date: datetime, frequency: str) -> List[Dict[str, datetime]]:
    """Generate list of date ranges based on frequency"""
    ranges = []
    current_start = start_date
    
    if frequency == "Weekly":
        # Handle the first partial week if start_date is not Monday
        if start_date.isoweekday() != 1:  # If not Monday
            # Find the next Sunday
            first_sunday = get_next_monday(start_date) - timedelta(days=1)
            first_sunday = min(first_sunday, end_date)
            
            ranges.append({
                "start": current_start,
                "end": first_sunday,
                "label": f"Week {current_start.strftime('%d %b')} - {first_sunday.strftime('%d %b %Y')}"
            })
            current_start = get_next_monday(start_date)
        
        # Handle full weeks and last partial week
        while current_start <= end_date:
            # Find this week's Sunday
            week_end = min(current_start + timedelta(days=6), end_date)  
            ranges.append({
                "start": current_start,
                "end": week_end,
                "label": f"Week {current_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}"
            })
            current_start = current_start + timedelta(days=7) 

    elif frequency == "Monthly":
        while current_start < end_date:
            if current_start.month == 12:
                month_end = current_start.replace(day=31)
            else:
                month_end = current_start.replace(day=1, month=current_start.month + 1) - timedelta(days=1)
            
            month_end = min(month_end, end_date)
            ranges.append({
                "start": current_start,
                "end": month_end,
                "label": current_start.strftime("%b %Y")
            })
            current_start = month_end + timedelta(days=1)

    elif frequency == "Quarterly":
        while current_start < end_date:
            quarter = (current_start.month - 1) // 3
            quarter_end_month = (quarter + 1) * 3
            if quarter_end_month == 12:
                quarter_end = current_start.replace(month=12, day=31)
            else:
                quarter_end = current_start.replace(month=quarter_end_month + 1, day=1) - timedelta(days=1)
            
            quarter_end = min(quarter_end, end_date)
            ranges.append({
                "start": current_start,
                "end": quarter_end,
                "label": f"Q{quarter + 1} {current_start.year}"
            })
            current_start = quarter_end + timedelta(days=1)

    elif frequency == "Yearly":
        while current_start < end_date:
            year_end = min(current_start.replace(month=12, day=31), end_date)
            ranges.append({
                "start": current_start,
                "end": year_end,
                "label": str(current_start.year)
            })
            current_start = year_end + timedelta(days=1)

    return ranges

def calculate_metrics_for_period(session_store, period_start: datetime, period_end: datetime) -> Dict[str, Union[str, int, float]]:
    """Calculate metrics for a specific time period"""
    # Get total sessions
    sessions = list(session_store.aggregate([
        {
            "$match": {
                "created_at": {
                    "$gte": period_start,
                    "$lt": period_end + timedelta(days=1),
                }
            }
        },
        {"$count": "count"},
    ]))

    # Get consented sessions with chat history
    consented_sessions = list(session_store.aggregate([
        {
            "$match": {
                "created_at": {
                    "$gte": period_start,
                    "$lt": period_end + timedelta(days=1),
                }
            }
        },
        {"$match": {"terms_of_service_consent.is_consented": True}},
        {"$addFields": {"session_id": {"$toString": "$_id"}}},
        {
            "$lookup": {
                "from": "chat_history",
                "localField": "session_id",
                "foreignField": "SessionId",
                "as": "chat_history",
            }
        },
        {
            "$project": {
                "data.access_token": 1,
                "logout": 1,
                "session_id": 1,
                "created_at": 1,
                "updated_at": 1,
                "chat_history": {"_id": 1, "History": 1},
            }
        },
    ]))

    # Filter chat sessions
    chat_sessions = list(filter(
        lambda session: len(session["chat_history"]) > 2,
        consented_sessions,
    ))

    # Calculate metrics
    session_count = sessions[0]["count"] if sessions else 0
    consented_session_count = len(consented_sessions)
    chat_session_count = len(chat_sessions)
    
    # Calculate click-through rate
    click_through_rate = round((consented_session_count / session_count) * 100, 2) if session_count > 0 else 0
    
    # Calculate message metrics
    total_chat_session_messages = reduce(
        lambda sum, session: sum + len(session["chat_history"]),
        chat_sessions,
        0,
    )
    
    avg_messages_count = round(
        total_chat_session_messages / chat_session_count, 2
    ) if chat_session_count > 0 else 0

    return {
        "period": period_start.strftime("%Y-%m-%d"),
        "session_count": session_count,
        "consented_session_count": consented_session_count,
        "click_through_rate": click_through_rate,
        "chat_session_count": chat_session_count,
        "avg_messages_count": avg_messages_count
    }

@app.get("/")
def read_root():
    return {"message": "Metrics API"}

@app.post("/api/metrics", response_model=List[MetricsResponse])
async def get_metrics(date_range: DateRange, bot_name: str):
    try:
        mongodb_connection = MongoDBConnection(db_name=bot_name)
        session_store = mongodb_connection.db[SESSION_STORE]

        # Parse dates
        start_date = datetime.strptime(date_range.start_date, "%Y-%m-%d").replace(tzinfo=TZ)
        end_date = datetime.strptime(date_range.end_date, "%Y-%m-%d").replace(tzinfo=TZ)
        
        # Generate date ranges based on frequency
        date_ranges = get_date_ranges(start_date, end_date, date_range.frequency)
        
        # Calculate metrics for each period
        metrics_by_period = []
        for date_range in date_ranges:
            period_metrics = calculate_metrics_for_period(
                session_store,
                date_range["start"],
                date_range["end"]
            )
            # Override the period with the formatted label
            period_metrics["period"] = date_range["label"]
            metrics_by_period.append(period_metrics)

        # Prepare response
        metrics = [
            MetricsResponse(
                metric="Total unique sessions",
                values=[MetricValue(period=m["period"], value=m["session_count"]) for m in metrics_by_period],
                remarks="Number of unique sessions created by period"
            ),
            MetricsResponse(
                metric="Total user consented sessions",
                values=[MetricValue(period=m["period"], value=m["consented_session_count"]) for m in metrics_by_period],
                remarks="Number of sessions with user consent by period"
            ),
            MetricsResponse(
                metric="Click Through Rate (CTR)",
                values=[MetricValue(period=m["period"], value=m["click_through_rate"]) for m in metrics_by_period],
                remarks="Percentage of users who consented by period"
            ),
            MetricsResponse(
                metric="Total chat sessions",
                values=[MetricValue(period=m["period"], value=m["chat_session_count"]) for m in metrics_by_period],
                remarks="Sessions with active chat interactions by period"
            ),
            MetricsResponse(
                metric="Average messages per chat session",
                values=[MetricValue(period=m["period"], value=m["avg_messages_count"]) for m in metrics_by_period],
                remarks="Average number of messages per session by period"
            )
        ]

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
