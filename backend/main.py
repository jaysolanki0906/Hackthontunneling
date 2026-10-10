from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os, uuid, random
from datetime import datetime, timedelta
from openai import OpenAI

app = FastAPI(title="Metro Tunnel RAG Backend")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", "your-api-key-here"))

FAULT_KB = {
    "E-04": "Door motor fault E-04: 1) Check 24V supply to door controller. 2) Inspect motor brushes for wear. 3) Verify encoder cable continuity. 4) Reset controller via DIP switch S3.",
    "E-07": "Traction inverter fault E-07: 1) Check DC link voltage (should be 750V ±5%). 2) Inspect IGBT gate driver board. 3) Clear fault via maintenance terminal CMD: RESET_INV.",
    "E-12": "Pantograph fault E-12: 1) Visually inspect pantograph head for damage. 2) Check pneumatic pressure (min 6 bar). 3) Test limit switches LS1 and LS2.",
}

ENGINEERS = [
    {"name": "Rajesh Kumar",  "badge": "ENG-047", "phone": "+91-98100-11234"},
    {"name": "Priya Sharma",  "badge": "ENG-023", "phone": "+91-98200-55678"},
    {"name": "Anil Verma",    "badge": "ENG-061", "phone": "+91-97300-99012"},
]

SYSTEM_PROMPT = """You are an expert metro maintenance assistant.
Answer ONLY based on the provided technical context.
Give numbered troubleshooting steps. Be concise and precise.
If the fault is critical, end with: ESCALATE_REQUIRED"""

class QueryRequest(BaseModel):
    fault: str

class EscalateRequest(BaseModel):
    fault: str
    steps_attempted: str

@app.post("/query")
async def handle_query(q: QueryRequest):
    fault_text = q.fault.upper()
    context = next(
        (v for k, v in FAULT_KB.items() if k in fault_text),
        "No specific fault code found in manuals. Provide general diagnostic steps.",
    )
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": f"Context: {context}\n\nTechnician query: {q.fault}"},
        ],
        max_tokens=300,
    )
    text = response.choices[0].message.content
    needs_escalation = "ESCALATE_REQUIRED" in text
    clean_text = text.replace("ESCALATE_REQUIRED", "").strip()
    return {"response": clean_text, "escalate_suggested": needs_escalation}

@app.post("/escalate")
async def escalate(req: EscalateRequest):
    engineer = random.choice(ENGINEERS)
    priority = "P1" if any(k in req.fault.upper() for k in ["E-07", "TRACTION", "BRAKE"]) else "P2"
    eta_minutes = 15 if priority == "P1" else 30
    eta_time = (datetime.now() + timedelta(minutes=eta_minutes)).strftime("%H:%M")

    # Use LLM to generate a concise fault summary for the ticket
    summary_resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Summarize this metro fault in one sentence for a maintenance ticket."},
            {"role": "user",   "content": f"Fault: {req.fault}\nSteps attempted: {req.steps_attempted}"},
        ],
        max_tokens=60,
    )
    summary = summary_resp.choices[0].message.content.strip()

    return {
        "ticketId":     f"TKT-{uuid.uuid4().hex[:6].upper()}",
        "engineer":     engineer,
        "eta":          eta_time,
        "priority":     priority,
        "faultSummary": summary,
        "createdAt":    datetime.now().strftime("%d %b %Y, %H:%M"),
    }

@app.get("/health")
async def health():
    return {"status": "ok"}
