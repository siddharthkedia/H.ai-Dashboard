from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import reduce
from typing import List, Dict, Optional
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
class MetricsResponse(BaseModel):
    metric: str
    value: float
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

# API Endpoints
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

        # Get total sessions
        sessions = list(session_store.aggregate([
                    {
                        "$match": {
                            "created_at": {
                                "$gte": start_date,
                                "$lt": end_date + timedelta(days=1),
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
                                        "$gte": start_date,
                                        "$lt": end_date + timedelta(days=1),
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

        # Prepare response
        metrics = [
            MetricsResponse(
                metric="Total unique sessions",
                value=session_count,
                remarks="Number of unique sessions created"
            ),
            MetricsResponse(
                metric="Total user consented sessions",
                value=consented_session_count,
                remarks="Number of sessions with user consent"
            ),
            MetricsResponse(
                metric="Click Through Rate (CTR)",
                value=click_through_rate,
                remarks="Percentage of users who consented"
            ),
            MetricsResponse(
                metric="Total chat sessions",
                value=chat_session_count,
                remarks="Sessions with active chat interactions"
            ),
            MetricsResponse(
                metric="Average messages per chat session",
                value=avg_messages_count,
                remarks="Average number of messages per session"
            )
        ]

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
