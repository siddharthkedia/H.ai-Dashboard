from fastapi import FastAPI
from pydantic import BaseModel
import random  # For demo purposes
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# Allow CORS for the frontend (React app) running on localhost:3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Allow only the React app to make requests
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Allow the necessary methods
    allow_headers=["*"],  # Allow any headers
)


# Define a model for comparison data
class ComparisonData(BaseModel):
    period: str
    value: float
@app.get("/")
def read_root():
    return {"message": "Hello, World!"}

@app.get("/api/compare-weekly")
async def compare_weekly():
    # Generate random data for testing (replace with actual DB query later)
    data = [ComparisonData(period=f"Week {i}", value=random.uniform(50, 200)) for i in range(1, 5)]
    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
