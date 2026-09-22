# PS 26133 Feature Implementation Plan — Complete Technical Blueprint

> **Goal:** Add all 6 missing features required by PS 26133 to MediKiosk
> **Approach:** Build on your existing Supabase + FastAPI + React architecture. All database interactions will strictly use the **Supabase Python SDK** (`supabase.table().select()...`). No raw SQL in the backend codebase.
> **Total Estimated Effort:** 8–12 days for a team, ~5–7 days if parallelized

---

## Feature 1: Queue & Appointment Management 🗓️

### What It Does
Implements a **Department-Level Priority Queue**. Patients register at the kiosk, join a department queue (e.g., General Medicine), and sit in the waiting area. Doctors don't get patients assigned in advance. When a doctor is free, they click "Next Patient," which pulls the highest-priority patient and assigns them to that doctor's room.

### Database Schema (add to `supabase_schema.sql`)
```sql
CREATE TABLE IF NOT EXISTS opd_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES dialogue_sessions(id) ON DELETE SET NULL,
    token_number INT NOT NULL,               -- e.g., 42 (resets daily)
    department TEXT NOT NULL DEFAULT 'General Medicine',
    doctor_id TEXT,                           -- Assigned when called
    room_number TEXT,                         -- Assigned when called
    status TEXT NOT NULL DEFAULT 'waiting',   -- 'waiting' | 'ready_for_doctor' | 'with_doctor' | 'completed'
    priority TEXT NOT NULL DEFAULT 'normal',  -- 'emergency' | 'urgent' | 'normal'
    registered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    called_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Backend API (`queue.py`)
```python
# Calling the next patient (Supabase SDK)
@router.post("/call-next")
async def call_next_patient(doctor_id: str, room_number: str, department: str):
    supabase = get_supabase_client()
    
    # Priority + FIFO pull
    queue = supabase.table("opd_queue") \
        .select("*, patients(name, phone)") \
        .eq("department", department) \
        .eq("status", "ready_for_doctor") \
        .order("priority", desc=True) \
        .order("registered_at", desc=False) \
        .limit(1) \
        .execute()
        
    if not queue.data:
        return {"message": "Queue is empty"}
        
    patient = queue.data[0]
    
    # Assign to doctor and room
    supabase.table("opd_queue") \
        .update({
            "doctor_id": doctor_id,
            "room_number": room_number,
            "status": "with_doctor",
            "called_at": datetime.utcnow().isoformat()
        }) \
        .eq("id", patient["id"]) \
        .execute()
        
    # Trigger SMS notification (optional)
    await notify_patient(patient["patients"]["phone"], patient["token_number"], room_number)
    
    return patient
```

---

## Feature 2: Facility Dashboard 📊

### What It Does
An admin dashboard showing aggregate metrics (patients today, average wait times, triage breakdown) using the Recharts library on the frontend. Powered entirely by Supabase aggregation queries.

### Backend API (`dashboard.py`)
```python
@router.get("/overview")
async def get_overview(department: str = None):
    supabase = get_supabase_client()
    
    # Get all today's queue entries
    query = supabase.table("opd_queue").select("*").gte("created_at", today_start)
    if department:
        query = query.eq("department", department)
        
    data = query.execute().data
    
    # Calculate metrics in Python
    total_patients = len(data)
    waiting = len([p for p in data if p["status"] in ["waiting", "ready_for_doctor"]])
    emergencies = len([p for p in data if p["priority"] == "emergency"])
    
    return {
        "total": total_patients,
        "waiting": waiting,
        "emergencies": emergencies
    }
```

---

## Feature 3: Referral Tracking 🔄

### What It Does
Tracks patients referred from PHCs to District Hospitals. Requires a new DB table, a backend API to create/update referrals, and simple UI forms for doctors to interact with.

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS referrals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
    referring_facility_id TEXT NOT NULL,
    referred_to_facility_id TEXT NOT NULL,
    reason TEXT NOT NULL,
    urgency TEXT NOT NULL DEFAULT 'routine',
    status TEXT NOT NULL DEFAULT 'initiated', -- 'initiated' | 'arrived' | 'completed'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Backend API (`referral.py`)
Provides `POST /referral/create` (used by doctor after consultation) and `PATCH /referral/update` (used by receiving hospital to mark 'arrived').

---

## Feature 4: Emergency Escalation (Powered by Jev AI) 🚨

### What It Does
Replaces the slower LLM red-flag prompt with **Jev**, a "System One" decision AI designed to output structured typed decisions in under 100ms. Runs *in parallel* with your normal intake.

### Backend API Integration
```python
import httpx

async def check_emergency_with_jev(patient_state: str) -> dict:
    """Uses Jev AI via OpenRouter for 100ms structured triage."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_KEY}"},
            json={
                "model": "typesafe/jev-latest",
                "state": patient_state,
                "questions": [
                    {
                        "type": "choice",
                        "name": "triage_level",
                        "options": ["EMERGENCY", "URGENT", "ROUTINE"]
                    },
                    {
                        "type": "noul",
                        "name": "needs_immediate_escalation"
                    }
                ]
            }
        )
        return response.json()

# In your intake pipeline:
triage_result = await check_emergency_with_jev(patient_transcript)

if triage_result["needs_immediate_escalation"]["probability"] > 0.90:
    # 1. Update queue priority to 'emergency' via Supabase
    # 2. Trigger Fast2SMS alert to duty doctors
    await send_emergency_sms(duty_doctors, "🚨 EMERGENCY ALERT: Patient Q-042...")
```

---

## Feature 5: Medicine Availability 💊

### What It Does
A manual inventory table (`medicine_inventory`) updated by pharmacy staff. When a SOAP note generates prescriptions, the system checks this table and highlights low/out-of-stock medicines on the doctor's screen.

### Database Schema
```sql
CREATE TABLE IF NOT EXISTS medicine_inventory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    facility_id TEXT NOT NULL,
    medicine_name TEXT NOT NULL,
    current_stock INT NOT NULL DEFAULT 0,
    reorder_level INT NOT NULL DEFAULT 50
);
```

---

## Feature 6: Follow-Up Reminders 👩‍⚕️

### What It Does
A `follow_up_registry` table that tracks high-risk patients. A background task runs daily to find patients whose follow-up is due and sends them an SMS reminder.

### Daily Cron Job
```python
async def send_daily_reminders():
    supabase = get_supabase_client()
    
    due_patients = supabase.table("follow_up_registry") \
        .select("*, patients(name, phone)") \
        .lte("next_follow_up_date", (today + timedelta(days=2)).isoformat()) \
        .eq("reminder_sms_sent", False) \
        .execute()
        
    for p in due_patients.data:
        await send_sms(p["patients"]["phone"], f"Reminder: Follow up due on {p['next_follow_up_date']}")
        supabase.table("follow_up_registry").update({"reminder_sms_sent": True}).eq("id", p["id"]).execute()
```

---
---

## 🎨 UI/UX Screen Requirements for Design Team

Please hand this section to your UI/UX designer. These are the **new screens** needed to support the features above.

### 1. Patient Queue TV Display (Waiting Area Screen)
**Purpose:** A large display screen (like in a bank or airport) mounted in the waiting room so patients know when they are called and which room to go to.
**Key UI Elements:**
- **"Now Calling" Section (Prominent):** Big text showing `Token Number → Room Number (Doctor Name)`. E.g., `🔔 Q-042 → Room 3 (Dr. Sharma)`
- **"Up Next" List (Side/Bottom):** A smaller list showing the next 3-4 tokens currently waiting.
- **Visuals:** High contrast, large fonts readable from a distance. Include a gentle chime/bell icon next to newly called numbers.

### 2. Kiosk "You are registered" Screen (Update to existing flow)
**Purpose:** The screen the patient sees immediately after logging in / verifying ABHA, before starting the voice interview.
**Key UI Elements:**
- **Your Token Number:** Big and clear (e.g., `Q-042`)
- **Queue Info:** "There are 5 patients ahead of you. Estimated wait: ~15 mins."
- **Instructions:** "Please complete your medical interview now while you wait."

### 3. Doctor's Queue Board (Tablet / Desktop Web App)
**Purpose:** The main interface for the doctor sitting in their consultation room to manage their patient flow.
**Key UI Elements:**
- **The "Call Next Patient" Button:** A massive primary button. When clicked, it pulls the next patient into their room.
- **The Live Queue Table:** A list of waiting patients in their department. Columns: Priority Icon (🚨/🟡/🟢), Token, Patient Name, Wait Time, Status (Waiting / Intake Complete).
- **Emergency Alert Banner:** A persistent sticky banner at the top if an emergency patient enters the queue.

### 4. Doctor's Consultation View (The "Patient Inside" Screen)
**Purpose:** What the doctor sees when a patient walks into the room.
**Key UI Elements:**
- **The SOAP Note / Vaidya Note:** The structured summary generated by the AI kiosk.
- **Medicine Availability Badges:** Next to the suggested prescription, show a small badge: `[✅ In Stock]` or `[❌ Out of Stock]`.
- **Refer Patient Button:** A secondary action button opening the Referral Modal.
- **Register Follow-Up Button:** A button to add the patient to the chronic care registry.

### 5. Facility Admin Dashboard (Desktop Web App)
**Purpose:** The overview screen for the hospital manager/CMO to monitor hospital performance.
**Key UI Elements:**
- **Top Metric Cards:** Total Patients, Avg Wait Time, Emergencies Today.
- **Charts (Recharts):** Line chart of patient volume over the week, Pie chart of Triage levels.
- **Alerts Panel (Right side):** Split into two lists:
  1. *Medicine Low-Stock Alerts*
  2. *Overdue Referrals / Follow-ups*

### 6. Two Simple Modals (Popups)
1. **Create Referral Modal:** Opened from the Doctor's Consultation View. Fields: Dropdown for Destination Hospital, Text area for Reason, Dropdown for Urgency.
2. **Update Medicine Stock Modal:** A simple form for pharmacy staff to click a medicine and type a new stock number.
