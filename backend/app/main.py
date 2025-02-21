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
    startDate: str
    endDate: str

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
async def get_metrics(dateRange: DateRange, botName: str):
    try:
        mongodbConnection = MongoDBConnection(db_name=botName)
        sessionStore = mongodbConnection.db[SESSION_STORE]

        # Parse dates
        startDate = datetime.strptime(dateRange.startDate, "%Y-%m-%d").replace(tzinfo=TZ)
        endDate = datetime.strptime(dateRange.endDate, "%Y-%m-%d").replace(tzinfo=TZ)
        
        # Aggregate all sessions in the date range
        sessions = list(sessionStore.aggregate([
            {
                "$match": {
                    "created_at": {
                        "$gte": startDate,
                        "$lte": endDate,
                    }
                }
            },
            {
                "$project": {
                    "created_at": 1,
                    "terms_of_service_consent.is_consented": 1,
                    "data.access_token": 1,
                    "logout": 1,
                    "_id": 1
                }
            },
            {
                "$addFields": {
                    "date": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$created_at"
                        }
                    },
                    "sessionId": {"$toString": "$_id"}
                }
            },
            {
                "$lookup": {
                    "from": "chat_history",
                    "localField": "sessionId",
                    "foreignField": "SessionId",
                    "as": "chatHistory"
                }
            }
        ]))

        # Group sessions by date and calculate metrics
        groupedSessions = {}
        for session in sessions:
            sessionDate = session['date']
            if sessionDate not in groupedSessions:
                groupedSessions[sessionDate] = {
                    "sessionCount": 0,
                    "consentedSessionCount": 0,
                    "chatSessionCount": 0,
                    "totalChatMessages": 0,
                    "totalChatMinutes": 0,
                    "maxMessagesInSession": 0,
                    "maxSessionLength": 0,
                    "otpLoggedInCount": 0,
                    "manuallyLoggedOutCount": 0
                }

            groupedSessions[sessionDate]["sessionCount"] += 1
            
            if session.get("terms_of_service_consent", {}).get("is_consented", False):
                groupedSessions[sessionDate]["consentedSessionCount"] += 1
                
                chatHistory = session.get("chatHistory", [])
                if len(chatHistory) > 2:
                    groupedSessions[sessionDate]["chatSessionCount"] += 1
                    groupedSessions[sessionDate]["totalChatMessages"] += len(chatHistory)
                    
                    # Calculate chat duration
                    if len(chatHistory) >= 2:
                        chatDuration = (chatHistory[-1]["_id"].generation_time - 
                                     chatHistory[0]["_id"].generation_time).total_seconds() / 60.0
                        groupedSessions[sessionDate]["totalChatMinutes"] += chatDuration
                        groupedSessions[sessionDate]["maxSessionLength"] = max(
                            groupedSessions[sessionDate]["maxSessionLength"], 
                            chatDuration
                        )
                    
                    groupedSessions[sessionDate]["maxMessagesInSession"] = max(
                        groupedSessions[sessionDate]["maxMessagesInSession"],
                        len(chatHistory)
                    )
                    
                    if session.get("data", {}).get("access_token"):
                        groupedSessions[sessionDate]["otpLoggedInCount"] += 1
                    
                    if session.get("logout"):
                        groupedSessions[sessionDate]["manuallyLoggedOutCount"] += 1

        # Prepare metrics for the response
        metricsByDate = []
        for date, data in groupedSessions.items():
            clickThroughRate = round((data["consentedSessionCount"] / data["sessionCount"]) * 100, 2) if data["sessionCount"] > 0 else 0
            avgMessagesCount = round(data["totalChatMessages"] / data["chatSessionCount"], 2) if data["chatSessionCount"] > 0 else 0
            avgSessionLength = round(data["totalChatMinutes"] / data["chatSessionCount"], 2) if data["chatSessionCount"] > 0 else 0
            totalChatHours = round(data["totalChatMinutes"] / 60.0, 2)

            metricsByDate.append({
                "period": date,
                "sessionCount": data["sessionCount"],
                "consentedSessionCount": data["consentedSessionCount"],
                "clickThroughRate": clickThroughRate,
                "chatSessionCount": data["chatSessionCount"],
                "totalChatMessages": data["totalChatMessages"],
                "avgMessagesCount": avgMessagesCount,
                "maxMessagesInSession": data["maxMessagesInSession"],
                "totalChatMinutes": round(data["totalChatMinutes"], 2),
                "totalChatHours": totalChatHours,
                "avgSessionLength": avgSessionLength,
                "maxSessionLength": round(data["maxSessionLength"], 2),
                "otpLoggedInCount": data["otpLoggedInCount"],
                "manuallyLoggedOutCount": data["manuallyLoggedOutCount"]
            })

        # Constructing the response
        metrics = [
            MetricsResponse(
                metric="Total unique sessions",
                values=[MetricValue(period=m["period"], value=m["sessionCount"]) for m in metricsByDate],
                remarks="Number of unique sessions created by date"
            ),
            MetricsResponse(
                metric="Total user consented sessions",
                values=[MetricValue(period=m["period"], value=m["consentedSessionCount"]) for m in metricsByDate],
                remarks="Number of sessions with user consent by date"
            ),
            MetricsResponse(
                metric="Click Through Rate (CTR)",
                values=[MetricValue(period=m["period"], value=m["clickThroughRate"]) for m in metricsByDate],
                remarks="Percentage of users who consented by date"
            ),
            MetricsResponse(
                metric="Total chat sessions",
                values=[MetricValue(period=m["period"], value=m["chatSessionCount"]) for m in metricsByDate],
                remarks="Sessions with active chat interactions by date"
            ),
            MetricsResponse(
                metric="Total chat session messages",
                values=[MetricValue(period=m["period"], value=m["totalChatMessages"]) for m in metricsByDate],
                remarks="Total number of chat messages in all sessions by date"
            ),
            MetricsResponse(
                metric="Average messages per chat session",
                values=[MetricValue(period=m["period"], value=m["avgMessagesCount"]) for m in metricsByDate],
                remarks="Average number of messages per session by date"
            ),
            MetricsResponse(
                metric="Maximum messages in a single chat session",
                values=[MetricValue(period=m["period"], value=m["maxMessagesInSession"]) for m in metricsByDate],
                remarks="Maximum number of messages in a single session by date"
            ),
            MetricsResponse(
                metric="Total engagement time (minutes)",
                values=[MetricValue(period=m["period"], value=m["totalChatMinutes"]) for m in metricsByDate],
                remarks="Total time spent by users chatting with the bot by date"
            ),
            MetricsResponse(
                metric="Total engagement time (hours)",
                values=[MetricValue(period=m["period"], value=m["totalChatHours"]) for m in metricsByDate],
                remarks="Total engagement time in hours by date"
            ),
            MetricsResponse(
                metric="Average engagement time per chat session (minutes)",
                values=[MetricValue(period=m["period"], value=m["avgSessionLength"]) for m in metricsByDate],
                remarks="Average time spent per chat session by date"
            ),
            MetricsResponse(
                metric="Maximum engagement time in a single chat session (minutes)",
                values=[MetricValue(period=m["period"], value=m["maxSessionLength"]) for m in metricsByDate],
                remarks="Longest single chat session duration by date"
            ),
            MetricsResponse(
                metric="OTP logged in chat sessions",
                values=[MetricValue(period=m["period"], value=m["otpLoggedInCount"]) for m in metricsByDate],
                remarks="Number of sessions with OTP authentication by date"
            ),
            MetricsResponse(
                metric="Manually logged out chat sessions",
                values=[MetricValue(period=m["period"], value=m["manuallyLoggedOutCount"]) for m in metricsByDate],
                remarks="Number of sessions where users manually logged out by date"
            )
        ]

        return metrics

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
