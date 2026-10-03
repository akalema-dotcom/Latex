from fastapi import FastAPI
from .db import Base, engine
from . import models

Base.metadata.create_all(bind=engine)
app=FastAPI(title="AI Business Workforce API",version="0.1.0")

@app.get("/health")
def health():
    return {"status":"ok","service":"ai-business-workforce","database":"connected"}

@app.get("/api/v1")
def api_info():
    return {"version":"v1","agents":["ATLAS","NOVA","ARIA","STOCK","MERCURY","LEDGER","INSIGHT","PULSE","ORBIT","SENTINEL"]}
