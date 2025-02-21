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
        
        # Aggregate all sessions in the date range
        sessions = list(session_store.aggregate([
            {
                "$match": {
                    "created_at": {
                        "$gte": start_date,
                        "$lte": end_date,
                    }
                }
            },
            {
                "$project": {
                    "created_at": 1,
                    "terms_of_service_consent.is_consented": 1,
                    "_id": 1
                }
            },
            # Add a date field for grouping
            {
                "$addFields": {
                    "date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    }
                }
            },
            {
                "$lookup": {
                    "from": "chat_history",
                    "localField": "_id",
                    "foreignField": "SessionId",
                    "as": "chat_history"
                }
            }
        ]))

        # Group sessions by date and calculate metrics
        grouped_sessions = {}
        for session in sessions:
            session_date = session['date']
            if session_date not in grouped_sessions:
                grouped_sessions[session_date] = {
                    "session_count": 0,
                    "consented_session_count": 0,
                    "chat_session_count": 0,
                    "total_chat_messages": 0
                }

            grouped_sessions[session_date]["session_count"] += 1
            if session["terms_of_service_consent"]["is_consented"]:
                grouped_sessions[session_date]["consented_session_count"] += 1
            if len(session["chat_history"]) > 2:
                grouped_sessions[session_date]["chat_session_count"] += 1
                grouped_sessions[session_date]["total_chat_messages"] += len(session["chat_history"])

        # Prepare metrics for the response
        metrics_by_date = []
        for date, data in grouped_sessions.items():
            click_through_rate = round((data["consented_session_count"] / data["session_count"]) * 100, 2) if data["session_count"] > 0 else 0
            avg_messages_count = round(
                data["total_chat_messages"] / data["chat_session_count"], 2
            ) if data["chat_session_count"] > 0 else 0

            metrics_by_date.append({
                "period": date,
                "session_count": data["session_count"],
                "consented_session_count": data["consented_session_count"],
                "click_through_rate": click_through_rate,
                "chat_session_count": data["chat_session_count"],
                "avg_messages_count": avg_messages_count
            })

        # Constructing the response
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
