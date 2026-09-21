# Sample Scenario: Low Priority vs High Priority Tasks

This document demonstrates how AISOS handles different priority levels with real examples.

---

## Scenario Overview

**Situation**: A company's IT department receives two service requests:
1. **Low Priority**: Password reset request (routine task)
2. **High Priority**: Database performance issue (business critical)

We'll demonstrate how the AI automatically classifies these requests and tracks their progress.

---

## Step 1: User Authentication

First, create an account and get your access token.

### Register a New User

```bash
curl -X POST
  -H "Content-Type: application/json" \
  -d '{
    "username": "IT Manager",
    "email": "manager@company.com",
    "password": "secure123"
  }'
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3Mzg0MTYwMDB9.abc123...",
  "user": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "IT Manager",
    "email": "manager@company.com"
  }
}
```

**💡 Save this token for all subsequent requests!**

```bash
# Export token as environment variable for easy use
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI1NTBlODQwMC1lMjliLTQxZDQtYTcxNi00NDY2NTU0NDAwMDAiLCJleHAiOjE3Mzg0MTYwMDB9.abc123..."
```

---

## Step 2: Create Low Priority Request

### Scenario: Employee Password Reset

An employee forgot their password - a routine, non-urgent task.

```bash
curl -X POST 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Password reset request for employee account",
    "description": "Hi, I forgot my password for my employee portal account. Can someone help me reset it when you get a chance? Not urgent, I can use the temporary access for now.",
    "requester_name": "Sarah Johnson",
    "requester_email": "sarah.johnson@company.com"
  }'
```

### AI Analysis - Low Priority Request

**Expected Response:**
```json
{
  "id": "req-low-priority-001",
  "title": "Password reset request for employee account",
  "description": "Hi, I forgot my password for my employee portal account...",
  "requester_name": "Sarah Johnson",
  "requester_email": "sarah.johnson@company.com",
  
  "category": "access",                    // ✓ AI Detected: "password", "account"
  "priority": "low",                       // ✓ AI Detected: No urgent keywords, neutral sentiment
  "status": "pending",
  "predicted_resolution_hours": 3.0,       // ✓ AI Predicted: access (2h) × low (1.5) = 3h
  
  "created_at": "2025-01-31T14:30:00Z",
  "updated_at": "2025-01-31T14:30:00Z",
  "assigned_to": null
}
```

### 🔍 Why Low Priority?

**AI Decision Logic:**
- ❌ No urgent keywords detected ("urgent", "critical", "emergency")
- ❌ No high priority keywords ("important", "blocked", "soon")
- ✓ Neutral/positive sentiment (polarity > -0.3)
- ✓ Category: "access" (keywords: "password", "account")
- **Result**: Priority = LOW

**Predicted Time Calculation:**
```
Base time for "access" category = 2.0 hours
Low priority multiplier = 1.5
Predicted time = 2.0 × 1.5 = 3.0 hours
```

---

## Step 3: Create High Priority Request

### Scenario: Database Performance Issues

The production database is experiencing performance degradation affecting customer transactions.

```bash
curl -X POST 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Important: Database performance degradation affecting sales",
    "description": "Our production database is running very slow and customers are experiencing delays during checkout. This is affecting our sales and needs priority attention soon. Multiple users have reported timeout errors.",
    "requester_name": "Mike Chen",
    "requester_email": "mike.chen@company.com"
  }'
```

### AI Analysis - High Priority Request

**Expected Response:**
```json
{
  "id": "req-high-priority-002",
  "title": "Important: Database performance degradation affecting sales",
  "description": "Our production database is running very slow...",
  "requester_name": "Mike Chen",
  "requester_email": "mike.chen@company.com",
  
  "category": "technical",                 // ✓ AI Detected: "database", "production", "timeout", "error"
  "priority": "high",                      // ✓ AI Detected: "important", "priority", "soon"
  "status": "pending",
  "predicted_resolution_hours": 6.0,       // ✓ AI Predicted: technical (8h) × high (0.75) = 6h
  
  "created_at": "2025-01-31T14:35:00Z",
  "updated_at": "2025-01-31T14:35:00Z",
  "assigned_to": null
}
```

### 🔍 Why High Priority?

**AI Decision Logic:**
- ✓ High priority keywords detected: "important", "priority", "soon"
- ✓ Business impact indicators: "affecting sales", "customers", "production"
- ✓ Negative sentiment (performance issues, delays, errors)
- ✓ Category: "technical" (keywords: "database", "production", "timeout", "error")
- **Result**: Priority = HIGH

**Predicted Time Calculation:**
```
Base time for "technical" category = 8.0 hours
High priority multiplier = 0.75
Predicted time = 8.0 × 0.75 = 6.0 hours
```

---

## Step 4: View All Requests in Dashboard

### Check Dashboard Statistics

```bash
curl -X GET
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "total_requests": 2,
  "pending_requests": 2,
  "in_progress_requests": 0,
  "resolved_requests": 0,
  "avg_resolution_time": 4.5,              // Average of 3.0h and 6.0h
  
  "category_distribution": {
    "access": 1,                            // Low priority request
    "technical": 1                          // High priority request
  },
  
  "priority_distribution": {
    "low": 1,                               // Password reset
    "high": 1                               // Database issue
  },
  
  "recent_requests": [
    {
      "id": "req-high-priority-002",
      "title": "Important: Database performance degradation...",
      "priority": "high",
      "status": "pending"
    },
    {
      "id": "req-low-priority-001",
      "title": "Password reset request...",
      "priority": "low",
      "status": "pending"
    }
  ]
}
```

---

## Step 5: Filter by Priority

### View Only High Priority Requests

```bash
curl -X GET
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "req-high-priority-002",
    "title": "Important: Database performance degradation affecting sales",
    "category": "technical",
    "priority": "high",
    "status": "pending",
    "predicted_resolution_hours": 6.0
  }
]
```

### View Only Low Priority Requests

```bash
curl -X GET 
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
[
  {
    "id": "req-low-priority-001",
    "title": "Password reset request for employee account",
    "category": "access",
    "priority": "low",
    "status": "pending",
    "predicted_resolution_hours": 3.0
  }
]
```

---

## Step 6: Update Request Progress

### Scenario: Start Working on High Priority Request First

Since the database issue is high priority, we should handle it first.

```bash
# Start progress on high priority request
curl -X PATCH 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "assigned_to": "Senior DB Admin"
  }'
```

**Response:**
```json
{
  "id": "req-high-priority-002",
  "title": "Important: Database performance degradation affecting sales",
  "status": "in_progress",                 // ✓ Status updated
  "assigned_to": "Senior DB Admin",        // ✓ Assigned
  "priority": "high",
  "predicted_resolution_hours": 6.0,
  "updated_at": "2025-01-31T14:40:00Z"    // ✓ Timestamp updated
}
```

### Check Dashboard - After Starting High Priority

```bash
curl -X 
  -H "Authorization: Bearer $TOKEN"
```

**Response:**
```json
{
  "total_requests": 2,
  "pending_requests": 1,                   // ✓ Decreased (low priority still pending)
  "in_progress_requests": 1,               // ✓ Increased (high priority in progress)
  "resolved_requests": 0,
  "avg_resolution_time": 4.5
}
```

---

## Step 7: Complete High Priority Request

After fixing the database issue:

```bash
curl -X 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved"
  }'
```

**Response:**
```json
{
  "id": "req-high-priority-002",
  "title": "Important: Database performance degradation affecting sales",
  "status": "resolved",                    // ✓ Completed
  "priority": "high",
  "updated_at": "2025-01-31T20:45:00Z"    // ✓ 6 hours later (matches prediction!)
}
```

---

## Step 8: Handle Low Priority Request

Now that the high priority task is done, start the password reset:

```bash
# Start progress on low priority request
curl -X PATCH 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "in_progress",
    "assigned_to": "Help Desk Agent"
  }'
```

**Response:**
```json
{
  "id": "req-low-priority-001",
  "title": "Password reset request for employee account",
  "status": "in_progress",
  "assigned_to": "Help Desk Agent",
  "priority": "low",
  "predicted_resolution_hours": 3.0,
  "updated_at": "2025-01-31T20:50:00Z"
}
```

### Complete Low Priority Request

```bash
curl -X PATCH 
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved"
  }'
```

---

## Step 9: Final Dashboard Check

```bash
curl -X GET 
  -H "Authorization: Bearer $TOKEN"
```

**Final State:**
```json
{
  "total_requests": 2,
  "pending_requests": 0,                   // ✓ All handled
  "in_progress_requests": 0,               // ✓ All completed
  "resolved_requests": 2,                  // ✓ Both resolved
  "avg_resolution_time": 4.5,
  
  "category_distribution": {
    "access": 1,
    "technical": 1
  },
  
  "priority_distribution": {
    "low": 1,
    "high": 1
  }
}
```

---

## 🎯 Key Takeaways from This Scenario

### Priority Comparison

| Aspect | Low Priority Request | High Priority Request |
|--------|---------------------|----------------------|
| **Keywords** | "forgot", "help", "when you get a chance" | "important", "priority", "soon", "affecting sales" |
| **Category** | Access | Technical |
| **AI Priority** | Low | High |
| **Predicted Time** | 3.0 hours | 6.0 hours |
| **Multiplier** | 1.5× (slower) | 0.75× (faster) |
| **Handling Order** | Second | First |
| **Business Impact** | Individual user | Multiple customers, sales impact |

### AI Classification Accuracy

✅ **Password Reset → Low Priority**
- Correctly identified routine access request
- No urgency indicators
- Appropriate resolution time

✅ **Database Issue → High Priority**
- Correctly identified business-critical issue
- Detected urgency and impact keywords
- Faster response time allocated

### Workflow Efficiency

**Traditional Manual Process:**
1. Both requests arrive
2. Admin manually reviews each
3. Admin decides priority
4. Admin assigns and tracks
5. **Time**: ~15-20 minutes per request for classification

**AISOS Automated Process:**
1. Both requests arrive
2. AI instantly classifies (< 50ms)
3. Auto-sorted by priority
4. Team sees prioritized queue
5. **Time**: Instant classification, immediate action

**Time Saved**: ~30 minutes per day with just 2 requests!

---

## 🎨 Visual Representation in UI

### Dashboard View

```
┌────────────────────────────────────────────────────┐
│  AISOS Dashboard                                   │
├────────────────────────────────────────────────────┤
│                                                    │
│  📊 Total: 2    ⏳ Pending: 0    ✅ Resolved: 2   │
│                                                    │
│  Priority Distribution:                            │
│  ┌─────────┬─────────┐                           │
│  │ 🔴 High │ 🟢 Low  │                           │
│  │   50%   │  50%    │                           │
│  └─────────┴─────────┘                           │
│                                                    │
│  Recent Activity:                                  │
│  ✅ Database issue - RESOLVED (High Priority)     │
│  ✅ Password reset - RESOLVED (Low Priority)      │
└────────────────────────────────────────────────────┘
```

---

## 🧪 Testing in Browser (UI Method)

### Step 1: Login
1. Go to: https://localhost
2. Register or login with credentials

### Step 2: Create Low Priority Request
1. Click **"New Request"** button
2. Fill in:
   - Title: `Password reset request for employee account`
   - Description: `Hi, I forgot my password. Can someone help when you get a chance?`
   - Name: `Sarah Johnson`
   - Email: `sarah.johnson@company.com`
3. Click **"Create Request"**
4. **Observe**: Badge shows "low" priority, category "access"

### Step 3: Create High Priority Request
1. Click **"New Request"** again
2. Fill in:
   - Title: `Important: Database performance issues`
   - Description: `Production database is slow, affecting sales. Need priority attention soon.`
   - Name: `Mike Chen`
   - Email: `mike.chen@company.com`
3. Click **"Create Request"**
4. **Observe**: Badge shows "high" priority, category "technical"

### Step 4: View Requests List
1. Click **"Requests"** in navigation
2. **Observe**: Both requests listed with color-coded badges
3. Try filters: Select "High" priority → See only database issue
4. Try filters: Select "Low" priority → See only password reset

### Step 5: Update Status
1. On high priority request, click **"Start Progress"**
2. Status changes to "In Progress"
3. Click **"Mark Resolved"**
4. Status changes to "Resolved"
5. Repeat for low priority request

### Step 6: Check Analytics
1. Click **"Analytics"** in navigation
2. View resolution rate: 100%
3. See distribution charts updated
4. Read AI insights section

---

## 📝 Summary

This scenario demonstrates:

✅ **AI automatically detects priority levels** based on keywords and sentiment  
✅ **Different categories get different base resolution times**  
✅ **Priority multipliers adjust response urgency**  
✅ **Dashboard provides real-time insights**  
✅ **Filters help focus on urgent tasks first**  
✅ **Status tracking shows progress through workflow**  
✅ **Analytics measure performance and efficiency**

**Result**: High priority issues get faster attention, while low priority tasks are handled efficiently without delays.

---

