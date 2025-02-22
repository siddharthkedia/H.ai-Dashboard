from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Union
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson.codec_options import CodecOptions
import time

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
    _client = None
    
    @classmethod
    def get_db(cls, db_name: str):
        if not cls._client:
            cls._client = MongoClient(MONGODB_URI)
        return cls._client[db_name].with_options(
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
                "duration": {
                    "$cond": {
                        "if": {"$gte": [{"$size": "$chatHistory"}, 2]},
                        "then": {
                            "$divide": [
                                {"$subtract": [
                                    {"$toDate": {"$arrayElemAt": ["$chatHistory._id", -1]}},
                                    {"$toDate": {"$arrayElemAt": ["$chatHistory._id", 0]}}
                                ]},
                                60000
                            ]
                        },
                        "else": 0
                    }
                },
                "hasAccessToken": {"$cond": {"if": {"$ifNull": ["$data.access_token", False]}, "then": 1, "else": 0}},
                "hasLogout": {"$cond": {"if": {"$ifNull": ["$logout", False]}, "then": 1, "else": 0}}
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
                "manualLogouts": {"$sum": "$hasLogout"},
                "avgMessages": {"$avg": "$chatHistorySize"},
                "avgDuration": {"$avg": "$duration"},
                "ctr": {
                    "$avg": {
                        "$cond": [
                            {"$eq": ["$sessionCount", 0]},
                            0,
                            {"$divide": ["$consented", "$sessionCount"]}
                        ]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 0,
                "date": "$_id",
                "sessionCount": 1,
                "consentedCount": 1,
                "chatSessionCount": 1,
                "totalMessages": 1,
                "totalDuration": 1,
                "maxMessages": 1,
                "maxDuration": 1,
                "otpLogins": 1,
                "manualLogouts": 1,
                "avgMessages": 1,
                "avgDuration": 1,
                "ctr": 1
            }
        },
        {"$sort": {"date": 1}}
    ]

@app.post("/api/metrics", response_model=List[MetricsResponse])
async def get_metrics(dateRange: DateRange, botName: str):
    try:
        start_time = time.time()
        
        # Get database connection
        db = MongoDBConnection.get_db(botName)
        sessions = db["sessions"]

        # Parse dates
        start_date = datetime.fromisoformat(dateRange.startDate).replace(tzinfo=TZ)
        end_date = datetime.fromisoformat(dateRange.endDate).replace(tzinfo=TZ)

        # Build and execute pipeline
        pipeline = create_aggregation_pipeline(start_date, end_date)
        cursor = sessions.aggregate(pipeline)
        daily_metrics = list(cursor)

        # Format response
        metrics_map = {
            "Total unique sessions": ("sessionCount", "Number of unique sessions created"),
            "User consented sessions": ("consentedCount", "Sessions with user consent"),
            "Click Through Rate (%)": ("ctr", "Percentage of consented sessions", lambda x: round((x or 0) * 100, 2)),
            "Active chat sessions": ("chatSessionCount", "Sessions with >2 messages"),
            "Total messages": ("totalMessages", "All messages across sessions"),
            "Avg messages/session": ("avgMessages", "Average messages per chat session", round),
            "Max messages (session)": ("maxMessages", "Most messages in a single session"),
            "Total engagement (minutes)": ("totalDuration", "Total chat time across sessions", round),
            "Avg session duration (minutes)": ("avgDuration", "Average chat session length", round),
            "Max duration (minutes)": ("maxDuration", "Longest chat session duration", round),
            "OTP logins": ("otpLogins", "Sessions with OTP authentication"),
            "Manual logouts": ("manualLogouts", "Explicit user logouts")
        }

        response = []
        for metric_name, (field, remark, *formatter) in metrics_map.items():
            formatter = formatter[0] if formatter else lambda x: x
            response.append(MetricsResponse(
                metric=metric_name,
                values=[MetricValue(period=m["date"], value=formatter(m[field])) for m in daily_metrics],
                remarks=remark
            ))

        print(f"Processed {len(daily_metrics)} days in {time.time() - start_time:.2f}s")
        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
