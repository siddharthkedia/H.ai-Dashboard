from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import reduce
from typing import List, Dict, Union
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson.codec_options import CodecOptions

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

# Pydantic models
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

# MongoDB Connection Class
class MongoDBConnection:
    def __init__(self, db_name: str):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[db_name].with_options(
            codec_options=CodecOptions(tz_aware=True, tzinfo=TZ)
        )

def calculate_metrics_for_date(session_store, date: datetime) -> Dict[str, Union[str, int, float]]:
    """Calculate metrics for a specific date"""
    day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = date.replace(hour=23, minute=59, second=59, microsecond=999999)

    # Get total sessions
    sessions = list(session_store.aggregate([
        {
            "$match": {
                "created_at": {
                    "$gte": day_start,
                    "$lte": day_end,
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
                    "$gte": day_start,
                    "$lte": day_end,
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
        "period": date.strftime("%d %b %Y"),
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
        
        # Calculate metrics for each day in the date range
        metrics_by_date = []
        current_date = start_date
        while current_date <= end_date:
            daily_metrics = calculate_metrics_for_date(session_store, current_date)
            metrics_by_date.append(daily_metrics)
            current_date += timedelta(days=1)

        # Prepare response
        metrics = [
            MetricsResponse(
                metric="Total unique sessions",
                values=[MetricValue(period=m["period"], value=m["session_count"]) for m in metrics_by_date],
                remarks="Number of unique sessions created by date"
            ),
            MetricsResponse(
                metric="Total user consented sessions",
                values=[MetricValue(period=m["period"], value=m["consented_session_count"]) for m in metrics_by_date],
                remarks="Number of sessions with user consent by date"
            ),
            MetricsResponse(
                metric="Click Through Rate (CTR)",
                values=[MetricValue(period=m["period"], value=m["click_through_rate"]) for m in metrics_by_date],
                remarks="Percentage of users who consented by date"
            ),
            MetricsResponse(
                metric="Total chat sessions",
                values=[MetricValue(period=m["period"], value=m["chat_session_count"]) for m in metrics_by_date],
                remarks="Sessions with active chat interactions by date"
            ),
            MetricsResponse(
                metric="Average messages per chat session",
                values=[MetricValue(period=m["period"], value=m["avg_messages_count"]) for m in metrics_by_date],
                remarks="Average number of messages per session by date"
            )
        ]

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
