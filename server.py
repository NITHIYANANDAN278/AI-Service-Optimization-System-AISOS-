from fastapi import FastAPI, APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import jwt
from passlib.context import CryptContext
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import TfidfVectorizer
import joblib
import re
from textblob import TextBlob
import json
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")

# Security
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()
SECRET_KEY = os.environ.get('JWT_SECRET', 'aisos-super-secret-key-2025')
ALGORITHM = "HS256"

# ML Models and Vectorizer
ML_MODELS = {}
VECTORIZER = None

# Configure Emergent LLM
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

# Chat session storage (in-memory for simplicity, use DB for production)
chat_sessions = {}

# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class User(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    username: str
    email: str
    created_at: str

class ServiceRequestCreate(BaseModel):
    title: str
    description: str
    requester_name: str
    requester_email: str

class ServiceRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    title: str
    description: str
    requester_name: str
    requester_email: str
    category: Optional[str] = None
    priority: Optional[str] = None
    status: str = "pending"
    predicted_resolution_hours: Optional[float] = None
    created_at: str
    updated_at: str
    assigned_to: Optional[str] = None

class ServiceRequestUpdate(BaseModel):
    status: Optional[str] = None
    assigned_to: Optional[str] = None

class DashboardStats(BaseModel):
    total_requests: int
    pending_requests: int
    in_progress_requests: int
    resolved_requests: int
    avg_resolution_time: float
    category_distribution: Dict[str, int]
    priority_distribution: Dict[str, int]
    recent_requests: List[ServiceRequest]

class ChatMessage(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str
    show_confirmation: bool = False
    request_data: Optional[Dict[str, str]] = None
    action_buttons: Optional[List[str]] = None

# Helper Functions
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=7)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if user is None:
            raise HTTPException(status_code=401, detail="User not found")
        return User(**user)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

# NLP Processing
def extract_features(text: str) -> Dict[str, Any]:
    """Extract NLP features from text"""
    text = text.lower()
    
    # Keywords for categories
    keywords = {
        'technical': ['software', 'hardware', 'network', 'computer', 'system', 'server', 'database', 'application', 'bug', 'error'],
        'maintenance': ['repair', 'fix', 'broken', 'maintenance', 'replace', 'install', 'update'],
        'access': ['password', 'login', 'access', 'permission', 'account', 'authentication'],
        'support': ['help', 'support', 'assistance', 'question', 'inquiry', 'information']
    }
    
    # Keywords for priority
    urgent_keywords = ['urgent', 'critical', 'emergency', 'asap', 'immediately', 'down', 'crash', 'failed']
    high_keywords = ['important', 'priority', 'soon', 'blocked', 'cannot', 'unable']
    
    # Sentiment analysis
    blob = TextBlob(text)
    sentiment = blob.sentiment.polarity
    
    # Detect category
    category_scores = {}
    for cat, words in keywords.items():
        score = sum(1 for word in words if word in text)
        category_scores[cat] = score
    
    detected_category = max(category_scores, key=category_scores.get) if category_scores else 'support'
    
    # Detect priority
    if any(word in text for word in urgent_keywords):
        detected_priority = 'urgent'
    elif any(word in text for word in high_keywords):
        detected_priority = 'high'
    elif sentiment < -0.3:
        detected_priority = 'medium'
    else:
        detected_priority = 'low'
    
    return {
        'category': detected_category,
        'priority': detected_priority,
        'sentiment': sentiment,
        'text_length': len(text),
        'word_count': len(text.split())
    }

def predict_resolution_time(category: str, priority: str) -> float:
    """Predict resolution time based on category and priority"""
    base_times = {
        'technical': 8.0,
        'maintenance': 12.0,
        'access': 2.0,
        'support': 4.0
    }
    
    priority_multipliers = {
        'urgent': 0.5,
        'high': 0.75,
        'medium': 1.0,
        'low': 1.5
    }
    
    base = base_times.get(category, 6.0)
    multiplier = priority_multipliers.get(priority, 1.0)
    
    # Add some randomness
    variance = np.random.normal(0, 0.1)
    return max(0.5, base * multiplier * (1 + variance))

# Authentication Routes
@api_router.post("/auth/register")
async def register(user_data: UserCreate):
    # Check if user exists
    existing_user = await db.users.find_one({"email": user_data.email}, {"_id": 0})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new user
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "username": user_data.username,
        "email": user_data.email,
        "password_hash": hash_password(user_data.password),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.users.insert_one(user_doc)
    
    token = create_access_token({"sub": user_id})
    
    return {
        "token": token,
        "user": {
            "id": user_id,
            "username": user_data.username,
            "email": user_data.email
        }
    }

@api_router.post("/auth/login")
async def login(credentials: UserLogin):
    user = await db.users.find_one({"email": credentials.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not verify_password(credentials.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user["id"]})
    
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"]
        }
    }

@api_router.get("/auth/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

# Service Request Routes
@api_router.post("/requests", response_model=ServiceRequest)
async def create_service_request(
    request_data: ServiceRequestCreate,
    current_user: User = Depends(get_current_user)
):
    # Extract features using NLP
    full_text = f"{request_data.title} {request_data.description}"
    features = extract_features(full_text)
    
    # Predict resolution time
    resolution_time = predict_resolution_time(features['category'], features['priority'])
    
    # Create request
    request_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    request_doc = {
        "id": request_id,
        "title": request_data.title,
        "description": request_data.description,
        "requester_name": request_data.requester_name,
        "requester_email": request_data.requester_email,
        "category": features['category'],
        "priority": features['priority'],
        "status": "pending",
        "predicted_resolution_hours": round(resolution_time, 2),
        "created_at": now,
        "updated_at": now,
        "assigned_to": None,
        "created_by_user_id": current_user.id
    }
    
    await db.service_requests.insert_one(request_doc)
    
    return ServiceRequest(**{k: v for k, v in request_doc.items() if k != "_id" and k != "created_by_user_id"})

@api_router.get("/requests", response_model=List[ServiceRequest])
async def get_service_requests(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    query = {}
    if status:
        query["status"] = status
    if category:
        query["category"] = category
    if priority:
        query["priority"] = priority
    
    requests = await db.service_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    return [ServiceRequest(**{k: v for k, v in req.items() if k != "created_by_user_id"}) for req in requests]

@api_router.get("/requests/{request_id}", response_model=ServiceRequest)
async def get_service_request(
    request_id: str,
    current_user: User = Depends(get_current_user)
):
    request = await db.service_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    return ServiceRequest(**{k: v for k, v in request.items() if k != "created_by_user_id"})

@api_router.patch("/requests/{request_id}", response_model=ServiceRequest)
async def update_service_request(
    request_id: str,
    update_data: ServiceRequestUpdate,
    current_user: User = Depends(get_current_user)
):
    request = await db.service_requests.find_one({"id": request_id}, {"_id": 0})
    if not request:
        raise HTTPException(status_code=404, detail="Request not found")
    
    update_fields = {k: v for k, v in update_data.model_dump().items() if v is not None}
    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.service_requests.update_one({"id": request_id}, {"$set": update_fields})
    
    updated_request = await db.service_requests.find_one({"id": request_id}, {"_id": 0})
    return ServiceRequest(**{k: v for k, v in updated_request.items() if k != "created_by_user_id"})

# Analytics Routes
@api_router.get("/analytics/dashboard", response_model=DashboardStats)
async def get_dashboard_stats(current_user: User = Depends(get_current_user)):
    all_requests = await db.service_requests.find({}, {"_id": 0}).to_list(10000)
    
    total = len(all_requests)
    pending = sum(1 for r in all_requests if r["status"] == "pending")
    in_progress = sum(1 for r in all_requests if r["status"] == "in_progress")
    resolved = sum(1 for r in all_requests if r["status"] == "resolved")
    
    # Calculate avg resolution time (using predicted for now)
    resolution_times = [r.get("predicted_resolution_hours", 0) for r in all_requests if r.get("predicted_resolution_hours")]
    avg_resolution = sum(resolution_times) / len(resolution_times) if resolution_times else 0
    
    # Category distribution
    category_dist = {}
    for r in all_requests:
        cat = r.get("category", "unknown")
        category_dist[cat] = category_dist.get(cat, 0) + 1
    
    # Priority distribution
    priority_dist = {}
    for r in all_requests:
        pri = r.get("priority", "low")
        priority_dist[pri] = priority_dist.get(pri, 0) + 1
    
    # Recent requests (last 5)
    recent = sorted(all_requests, key=lambda x: x["created_at"], reverse=True)[:5]
    
    return DashboardStats(
        total_requests=total,
        pending_requests=pending,
        in_progress_requests=in_progress,
        resolved_requests=resolved,
        avg_resolution_time=round(avg_resolution, 2),
        category_distribution=category_dist,
        priority_distribution=priority_dist,
        recent_requests=[ServiceRequest(**{k: v for k, v in r.items() if k != "created_by_user_id"}) for r in recent]
    )

@api_router.get("/analytics/trends")
async def get_trends(current_user: User = Depends(get_current_user)):
    """Get request trends over time"""
    all_requests = await db.service_requests.find({}, {"_id": 0}).to_list(10000)
    
    # Group by date
    daily_counts = {}
    for r in all_requests:
        date = r["created_at"][:10]  # Get YYYY-MM-DD
        daily_counts[date] = daily_counts.get(date, 0) + 1
    
    # Sort by date
    sorted_dates = sorted(daily_counts.items())
    
    return {
        "daily_requests": [{
            "date": date,
            "count": count
        } for date, count in sorted_dates[-30:]]  # Last 30 days
    }

# Chatbot Route with Service Request Creation
@api_router.post("/chat", response_model=ChatResponse)
async def chat_with_bot(
    chat_message: ChatMessage,
    current_user: User = Depends(get_current_user)
):
    """Chat with AI assistant - can create service requests through conversation"""
    try:
        if not EMERGENT_LLM_KEY:
            raise HTTPException(status_code=500, detail="LLM API key not configured")
        
        user_message = chat_message.message.strip()
        session_id = f"chat_{current_user.id}"
        
        # Get or create session state
        if session_id not in chat_sessions:
            chat_sessions[session_id] = {
                "state": "idle",  # idle, collecting_details, awaiting_confirmation
                "request_data": {},
                "missing_fields": []
            }
        
        session = chat_sessions[session_id]
        
        # Handle confirmation actions
        if user_message.lower() in ["yes", "confirm", "create", "proceed"]:
            if session["state"] == "awaiting_confirmation":
                # Create the service request
                request_data = session["request_data"]
                
                # Extract features using NLP
                full_text = f"{request_data['title']} {request_data['description']}"
                features = extract_features(full_text)
                resolution_time = predict_resolution_time(features['category'], features['priority'])
                
                # Create request
                request_id = str(uuid.uuid4())
                now = datetime.now(timezone.utc).isoformat()
                
                request_doc = {
                    "id": request_id,
                    "title": request_data['title'],
                    "description": request_data['description'],
                    "requester_name": request_data['name'],
                    "requester_email": request_data['email'],
                    "category": features['category'],
                    "priority": features['priority'],
                    "status": "pending",
                    "predicted_resolution_hours": round(resolution_time, 2),
                    "created_at": now,
                    "updated_at": now,
                    "assigned_to": None,
                    "created_by_user_id": current_user.id
                }
                
                await db.service_requests.insert_one(request_doc)
                
                # Reset session
                session["state"] = "idle"
                session["request_data"] = {}
                session["missing_fields"] = []
                
                response_text = f"✅ **Service Request Created Successfully!**\n\n"
                response_text += f"**Request ID:** {request_id}\n"
                response_text += f"**Title:** {request_data['title']}\n"
                response_text += f"**Category:** {features['category'].title()}\n"
                response_text += f"**Priority:** {features['priority'].title()}\n"
                response_text += f"**Predicted Resolution Time:** {round(resolution_time, 2)} hours\n\n"
                response_text += f"Your request has been submitted and is now pending review. You can track its status in the Requests page."
                
                return ChatResponse(response=response_text)
        
        # Handle cancellation
        if user_message.lower() in ["no", "cancel", "stop", "abort"]:
            if session["state"] in ["collecting_details", "awaiting_confirmation"]:
                session["state"] = "idle"
                session["request_data"] = {}
                session["missing_fields"] = []
                return ChatResponse(response="Service request creation cancelled. How else can I help you?")
        
        # Detect if user wants to create a service request
        create_intent_keywords = [
            "create request", "new request", "service request", "want to create",
            "create a request", "make a request", "submit request", "open ticket"
        ]
        
        is_create_intent = any(keyword in user_message.lower() for keyword in create_intent_keywords)
        
        # If user wants to create a request and NOT already in confirmation state
        if is_create_intent and session["state"] != "awaiting_confirmation":
            session["state"] = "collecting_details"
            session["request_data"] = {}
            session["missing_fields"] = ["title", "description", "name", "email"]
            
            response_text = "Great! I'll help you create a service request.\n\n"
            response_text += "Please provide all the following details in ONE message:\n\n"
            response_text += "**Title:** [Brief summary of your issue]\n"
            response_text += "**Description:** [Detailed explanation]\n"
            response_text += "**Name:** [Your full name]\n"
            response_text += "**Email:** [Your email address]\n\n"
            response_text += "Example: Title: Server Down, Description: Production server crashed, Name: John Doe, Email: john@company.com"
            
            return ChatResponse(response=response_text)
        
        # If we're collecting details
        if session["state"] == "collecting_details":
            # Parse the message for fields
            message_lower = user_message.lower()
            
            # Try to extract fields from the message
            if "title:" in message_lower or "issue:" in message_lower:
                # Extract title
                title_match = re.search(r'(?:title|issue):\s*([^,\n]+)', user_message, re.IGNORECASE)
                if title_match:
                    session["request_data"]["title"] = title_match.group(1).strip()
                    if "title" in session["missing_fields"]:
                        session["missing_fields"].remove("title")
            
            if "description:" in message_lower or "details:" in message_lower:
                # Extract description
                desc_match = re.search(r'(?:description|details):\s*([^,\n]+(?:\n[^:]*)?)', user_message, re.IGNORECASE)
                if desc_match:
                    session["request_data"]["description"] = desc_match.group(1).strip()
                    if "description" in session["missing_fields"]:
                        session["missing_fields"].remove("description")
            
            if "name:" in message_lower:
                # Extract name
                name_match = re.search(r'name:\s*([^,\n]+)', user_message, re.IGNORECASE)
                if name_match:
                    session["request_data"]["name"] = name_match.group(1).strip()
                    if "name" in session["missing_fields"]:
                        session["missing_fields"].remove("name")
            
            if "email:" in message_lower or "@" in user_message:
                # Extract email
                email_match = re.search(r'(?:email:\s*)?([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', user_message, re.IGNORECASE)
                if email_match:
                    session["request_data"]["email"] = email_match.group(1).strip()
                    if "email" in session["missing_fields"]:
                        session["missing_fields"].remove("email")
            
            # If no structured format found and user provided free text, try to be smart
            if not any(field in session["request_data"] for field in ["title", "description"]) and len(user_message) > 10:
                # If message looks like a description of an issue, treat it as such
                if "title" in session["missing_fields"] and "description" in session["missing_fields"]:
                    # Split into title (first sentence) and description (rest)
                    sentences = user_message.split('.')
                    if len(sentences) > 1:
                        session["request_data"]["title"] = sentences[0].strip()
                        session["request_data"]["description"] = '. '.join(sentences[1:]).strip()
                        session["missing_fields"].remove("title")
                        session["missing_fields"].remove("description")
                    else:
                        session["request_data"]["title"] = user_message[:100]
                        session["request_data"]["description"] = user_message
                        session["missing_fields"].remove("title")
                        session["missing_fields"].remove("description")
            
            # Check if all fields are collected
            if not session["missing_fields"]:
                # All fields collected, show confirmation
                session["state"] = "awaiting_confirmation"
                
                response_text = "📋 **Please review your service request:**\n\n"
                response_text += f"**Title:** {session['request_data']['title']}\n\n"
                response_text += f"**Description:** {session['request_data']['description']}\n\n"
                response_text += f"**Name:** {session['request_data']['name']}\n\n"
                response_text += f"**Email:** {session['request_data']['email']}\n\n"
                response_text += "Would you like to create this service request?"
                
                return ChatResponse(
                    response=response_text,
                    show_confirmation=True,
                    request_data=session["request_data"],
                    action_buttons=["Confirm", "Cancel"]
                )
            else:
                # Still missing fields
                response_text = "Thanks! I still need the following:\n\n"
                for field in session["missing_fields"]:
                    response_text += f"• **{field.title()}**\n"
                response_text += "\nPlease provide these details."
                
                return ChatResponse(response=response_text)
        
        # Regular chat - use LLM
        # Get user's recent requests for context
        user_requests = await db.service_requests.find(
            {"created_by_user_id": current_user.id},
            {"_id": 0}
        ).sort("created_at", -1).limit(5).to_list(5)
        
        system_message = """You are a helpful AI assistant for AISOS (AI-Driven Service Optimization System).

AISOS is a service request management platform that uses AI to automatically:
- Classify service requests into categories (Technical, Maintenance, Access, Support)
- Assign priority levels (Urgent, High, Medium, Low)
- Predict resolution time
- Provide analytics and insights

You can help users with:
- General questions about AISOS features
- Checking request status
- Understanding analytics and insights
- Explaining how the system works

IMPORTANT: If user asks about creating a service request or mentions an issue, tell them:
"To create a service request, please say 'I want to create a request' and I'll guide you through the process."

Be friendly, concise, and helpful. Keep responses short."""

        # Initialize chat with Emergent LLM
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=session_id,
            system_message=system_message
        ).with_model("gemini", "gemini-2.5-flash")
        
        # Create user message with context
        context_text = f"Current user: {current_user.username} ({current_user.email})\n"
        if user_requests:
            context_text += f"User has {len(user_requests)} recent requests:\n"
            for req in user_requests[:3]:
                context_text += f"- {req['title']} (Status: {req['status']})\n"
        
        full_message = f"{context_text}\n\nUser question: {user_message}"
        
        user_msg = UserMessage(text=full_message)
        response = await chat.send_message(user_msg)
        
        return ChatResponse(response=response)
    
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

# Root
@api_router.get("/")
async def root():
    return {"message": "AISOS API - AI-Driven Service Optimization System"}

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup():
    logger.info("AISOS Backend Started")
    # Create indexes for better performance
    await db.users.create_index("email", unique=True)
    await db.service_requests.create_index("created_at")
    await db.service_requests.create_index("status")

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()