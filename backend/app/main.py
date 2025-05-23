from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from typing import List, Union
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from bson.codec_options import CodecOptions
import time
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()
allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Constants
TZ = ZoneInfo(os.getenv("APP_TIMEZONE"))
MONGODB_URI = os.getenv("MONGODB_URI")

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
    pipeline = [
        # Stage 1: Filter sessions by date
        {
            "$match": {
                "created_at": {"$gte": start_date, "$lte": end_date}
            }
        },
        # Stage 2: Prepare lookup key
        {
            "$addFields": {
                "sessionIdStr": {"$toString": "$_id"}
            }
        },
        # Stage 3: Lookup chat history
        {
            "$lookup": {
                "from": "chat_history",
                "localField": "sessionIdStr",
                "foreignField": "SessionId",
                "as": "chatHistory"
            }
        },
        # Stage 4: Compute chat history size
        {
            "$addFields": {
                "chatHistorySize": {"$size": "$chatHistory"}
            }
        },
        # Stage 5: Derive additional fields based on chatHistorySize
        {
            "$addFields": {
                "isChatSession": {"$gt": ["$chatHistorySize", 2]},
                "duration": {
                    "$cond": {
                        "if": {"$gt": ["$chatHistorySize", 2]},
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
                "hasAccessToken": {
                    "$cond": {
                        "if": {"$ifNull": ["$data.access_token", False]},
                        "then": 1,
                        "else": 0
                    }
                },
                "hasLogout": {
                    "$cond": {
                        "if": {"$ifNull": ["$logout", False]},
                        "then": 1,
                        "else": 0
                    }
                }
            }
        },
        # Stage 6: Remove the bulky chatHistory array to reduce payload size in grouping
        {
            "$project": {
                "chatHistory": 0
            }
        },
        # Stage 7: Group by day and calculate raw metrics only
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
                "consentedCount": {"$sum": {"$cond": [{"$ifNull": ["$terms_of_service_consent.is_consented", False]}, 1, 0]}},
                "chatSessionCount": {"$sum": {"$cond": ["$isChatSession", 1, 0]}},
                "totalMessages": {"$sum": {"$cond": ["$isChatSession", "$chatHistorySize", 0]}},
                "totalDuration": {"$sum": {"$cond": ["$isChatSession", "$duration", 0]}},
                "maxMessages": {"$max": {"$cond": ["$isChatSession", "$chatHistorySize", 0]}},
                "maxDuration": {"$max": {"$cond": ["$isChatSession", "$duration", 0]}},
                "otpLogins": {"$sum": {"$cond": ["$isChatSession", "$hasAccessToken", 0]}},
                "manualLogouts": {"$sum": {"$cond": ["$isChatSession", "$hasLogout", 0]}},
            }
        },
        # Stage 8: Final projection (only raw metrics)
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
                "manualLogouts": 1
            }
        },
    ]
    return pipeline

@app.post("/api/metrics", response_model=List[MetricsResponse])
async def get_metrics(dateRange: DateRange, botName: str):
    try:
        start_time = time.time()
        
        # Get database connection
        db = MongoDBConnection.get_db(botName)
        sessions = db["sessions"]

        # Parse dates
        start_date = datetime.fromisoformat(dateRange.startDate).replace(tzinfo=TZ)
        end_date = datetime.fromisoformat(dateRange.endDate).replace(tzinfo=TZ) + timedelta(days=1)

        # Build and execute pipeline
        pipeline = create_aggregation_pipeline(start_date, end_date)
        cursor = sessions.aggregate(pipeline)
        daily_metrics = list(cursor)

        metrics_map = {
            "Total unique sessions": ("sessionCount", "Number of unique sessions created"),
            "User consented sessions": ("consentedCount", "Sessions with user consent"),
            "Active chat sessions": ("chatSessionCount", "Sessions with >2 messages"),
            "Total messages (active chat sessions)": ("totalMessages", "All messages in active chat sessions"),
            "Max messages (active chat session)": ("maxMessages", "Most messages in a single active chat session"),
            "Total engagement (minutes, active chat sessions)": ("totalDuration", "Total chat time in active chat sessions", round),
            "Max duration (minutes, active chat session)": ("maxDuration", "Longest chat session duration among active sessions", round),
            "OTP logins (active chat sessions)": ("otpLogins", "Sessions with OTP authentication in active chat sessions"),
            "Manual logouts (active chat sessions)": ("manualLogouts", "Sessions with manual logout in active chat sessions")
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
    uvicorn.run(app, host=os.getenv("API_HOST", "0.0.0.0"), port=int(os.getenv("API_PORT", 8000)))
