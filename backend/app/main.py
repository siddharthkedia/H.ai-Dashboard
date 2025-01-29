from fastapi import FastAPI, Depends
# from backend.app.h_ai_metrics import get_db
# from backend.app.models import DataComparison
from pymongo import MongoClient
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import random  # For demo purposes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# # Dependency to get the MongoDB database
# def get_collection():
#     db = get_db()
#     return db["data_comparison"]  # Access the data_comparison collection in MongoDB

# Allow CORS for the frontend (React app) running on localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow only the React app to make requests
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"], 
    allow_headers=["*"], 
)


class ComparisonData(BaseModel):
    period: str
    value: float

# Hardcoded data for metrics
metrics_data = {
    "totalUniqueSessions": 1200,
    "totalUserConsentedSessions": 950,
    "ctr": 15.5,  # Click Through Rate in percentage
    "totalChatSessions": 800,
    "totalChatMessages": 15000,
    "avgMessagesPerSession": 18.75,
    "maxMessagesInSession": 200,
    "totalEngagementTime": 5500,  # In minutes
    "avgEngagementTimePerSession": 7,
    "maxEngagementTimeInSession": 120,
    "otpLoggedInSessions": 300,
    "manuallyLoggedOutSessions": 50,
}

@app.get("/api/metrics")
async def get_metrics():
    return JSONResponse(content=metrics_data)

@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/api/compare-weekly")
async def compare_weekly():#db: MongoClient = Depends(get_db)):
#     collection = get_collection()
#     # Fetch documents where the period is 'Week'
#     comparison_data = list(collection.find({"period": "Week"}))  # Fetch as a list
#     return comparison_data  # Return as JSON response

    
# @app.post("/api/compare-weekly")
# async def add_data():#data: DataComparison, db: MongoClient = Depends(get_db)):
#     # collection = get_collection()
#     # # Insert a new document into the collection
#     # result = collection.insert_one(data.dict())  # Convert the Pydantic model to a dict
#     # return {"message": "Data added", "id": str(result.inserted_id)}

    # Generate random data for testing (replace with actual DB query later)
    data = [ComparisonData(period=f"Week {i}", value=random.uniform(50, 200)) for i in range(1, 5)]
    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
