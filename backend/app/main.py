from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Union
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson.codec_options import CodecOptions

app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
TZ = ZoneInfo("Asia/Kolkata")
MONGODB_URI = "mongodb+srv://dbadmin:WgF8i17BVrhMveS@hfcl-genai-cosmon-cin-001-uat.mongocluster.cosmos.azure.com/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"

# Pydantic Models
class MetricValue(BaseModel):
    period: str
    value: Union[int, float]

class MetricsResponse(BaseModel):
    metric: str
    values: List[MetricValue]
    remarks: str

class DateRange(BaseModel):
    startDate: str
    endDate: str

# MongoDB Connection Handler
class MongoDBConnection:
    def __init__(self, db_name: str):
        self.client = MongoClient(MONGODB_URI)
        self.db = self.client[db_name].with_options(
            codec_options=CodecOptions(tz_aware=True, tzinfo=TZ)
        )

def create_aggregation_pipeline(start_date: datetime, end_date: datetime) -> list:
    return [
        {
            "$match": {
                "created_at": {"$gte": start_date, "$lte": end_date}
            }
        },
        {
            "$project": {
                "created_at": 1,
                "terms_of_service_consent.is_consented": 1,
                "data.access_token": 1,
                "logout": 1,
                "_id": {"$toString": "$_id"}
            }
        },
        {
            "$lookup": {
                "from": "chat_history",
                "localField": "_id",
                "foreignField": "SessionId",
                "as": "chatHistory"
            }
        },
        {
            "$addFields": {
                "consented": {"$cond": {"if": "$terms_of_service_consent.is_consented", "then": 1, "else": 0}},
                "chatHistorySize": {"$size": "$chatHistory"},
                "isChatSession": {"$gt": [{"$size": "$chatHistory"}, 2]},
                "firstMessage": {"$arrayElemAt": ["$chatHistory._id", 0]},
                "lastMessage": {"$arrayElemAt": ["$chatHistory._id", -1]},
                "hasAccessToken": {"$cond": {"if": {"$ifNull": ["$data.access_token", False]}, "then": 1, "else": 0}},
                "hasLogout": {"$cond": {"if": {"$ifNull": ["$logout", False]}, "then": 1, "else": 0}}
            }
        },
        {
            "$addFields": {
                "duration": {
                    "$cond": {
                        "if": {"$gte": ["$chatHistorySize", 2]},
                        "then": {
                            "$divide": [
                                {"$subtract": [
                                    {"$toDate": "$lastMessage"},
                                    {"$toDate": "$firstMessage"}
                                ]},
                                60000  # Convert milliseconds to minutes
                            ]
                        },
                        "else": 0
                    }
                }
            }
        },
        {
            "$group": {
                "_id": {
                    "$dateToString": {
                        "format": "%Y-%m-%d",
                        "date": "$created_at",
                        "timezone": "Asia/Kolkata"
                    }
                },
                "sessionCount": {"$sum": 1},
                "consentedCount": {"$sum": "$consented"},
                "chatSessionCount": {"$sum": {"$cond": ["$isChatSession", 1, 0]}},
                "totalMessages": {"$sum": "$chatHistorySize"},
                "totalDuration": {"$sum": "$duration"},
                "maxMessages": {"$max": "$chatHistorySize"},
                "maxDuration": {"$max": "$duration"},
                "otpLogins": {"$sum": "$hasAccessToken"},
                "manualLogouts": {"$sum": "$hasLogout"}
            }
        },
        {"$sort": {"_id": 1}}
    ]

@app.post("/api/metrics", response_model=List[MetricsResponse])
async def get_metrics(dateRange: DateRange, botName: str):
    try:
        # Initialize connection
        conn = MongoDBConnection(botName)
        sessions = conn.db["sessions"]

        # Parse dates with timezone
        start_date = datetime.fromisoformat(dateRange.startDate).replace(tzinfo=TZ)
        end_date = datetime.fromisoformat(dateRange.endDate).replace(tzinfo=TZ)

        # Execute aggregation pipeline
        pipeline = create_aggregation_pipeline(start_date, end_date)
        daily_metrics = list(sessions.aggregate(pipeline))

        # Process results
        metrics = []
        for day in daily_metrics:
            # Calculate derived metrics
            ctr = (day["consentedCount"] / day["sessionCount"]) * 100 if day["sessionCount"] else 0
            avg_messages = day["totalMessages"] / day["chatSessionCount"] if day["chatSessionCount"] else 0
            avg_duration = day["totalDuration"] / day["chatSessionCount"] if day["chatSessionCount"] else 0
            
            metrics.append({
                "period": day["_id"],
                "sessionCount": day["sessionCount"],
                "consentedCount": day["consentedCount"],
                "ctr": round(ctr, 2),
                "chatSessions": day["chatSessionCount"],
                "totalMessages": day["totalMessages"],
                "avgMessages": round(avg_messages, 2),
                "maxMessages": day["maxMessages"],
                "totalMinutes": round(day["totalDuration"], 2),
                "avgDuration": round(avg_duration, 2),
                "maxDuration": round(day["maxDuration"], 2),
                "otpLogins": day["otpLogins"],
                "manualLogouts": day["manualLogouts"]
            })

        # Build response
        return [
            MetricsResponse(
                metric="Total unique sessions",
                values=[MetricValue(period=m["period"], value=m["sessionCount"]) for m in metrics],
                remarks="Number of unique sessions created"
            ),
            MetricsResponse(
                metric="User consented sessions",
                values=[MetricValue(period=m["period"], value=m["consentedCount"]) for m in metrics],
                remarks="Sessions with user consent"
            ),
            MetricsResponse(
                metric="Click Through Rate (%)",
                values=[MetricValue(period=m["period"], value=m["ctr"]) for m in metrics],
                remarks="Percentage of consented sessions"
            ),
            MetricsResponse(
                metric="Active chat sessions",
                values=[MetricValue(period=m["period"], value=m["chatSessions"]) for m in metrics],
                remarks="Sessions with >2 messages"
            ),
            MetricsResponse(
                metric="Total messages",
                values=[MetricValue(period=m["period"], value=m["totalMessages"]) for m in metrics],
                remarks="All messages across sessions"
            ),
            MetricsResponse(
                metric="Avg messages/session",
                values=[MetricValue(period=m["period"], value=m["avgMessages"]) for m in metrics],
                remarks="Average messages per chat session"
            ),
            MetricsResponse(
                metric="Max messages (session)",
                values=[MetricValue(period=m["period"], value=m["maxMessages"]) for m in metrics],
                remarks="Most messages in a single session"
            ),
            MetricsResponse(
                metric="Total engagement (minutes)",
                values=[MetricValue(period=m["period"], value=m["totalMinutes"]) for m in metrics],
                remarks="Total chat time across sessions"
            ),
            MetricsResponse(
                metric="Avg session duration (minutes)",
                values=[MetricValue(period=m["period"], value=m["avgDuration"]) for m in metrics],
                remarks="Average chat session length"
            ),
            MetricsResponse(
                metric="Max duration (minutes)",
                values=[MetricValue(period=m["period"], value=m["maxDuration"]) for m in metrics],
                remarks="Longest chat session duration"
            ),
            MetricsResponse(
                metric="OTP logins",
                values=[MetricValue(period=m["period"], value=m["otpLogins"]) for m in metrics],
                remarks="Sessions with OTP authentication"
            ),
            MetricsResponse(
                metric="Manual logouts",
                values=[MetricValue(period=m["period"], value=m["manualLogouts"]) for m in metrics],
                remarks="Explicit user logouts"
            )
        ]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
