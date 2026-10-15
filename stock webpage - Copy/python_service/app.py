from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import fitz  # PyMuPDF
import pdfplumber
import requests
import os
import tempfile
import re

app = FastAPI(title="Deep Indian Equity Research - DocIntel Microservice")

class DocumentRequest(BaseModel):
    url: str
    symbol: str

class ExtractedFact(BaseModel):
    metric: str
    value: str
    period: str
    confidence: float

class DocumentResponse(BaseModel):
    symbol: str
    facts: list[ExtractedFact]
    raw_text_length: int

def download_pdf(url: str, temp_path: str):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, stream=True, timeout=15)
    if response.status_code != 200:
        raise Exception(f"Failed to download PDF. HTTP {response.status_code}")
    with open(temp_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

def extract_facts_from_text(text: str) -> list[ExtractedFact]:
    facts = []
    text_lower = text.lower()
    
    # Very basic regex extractions for demonstration. 
    # In a full production system, this would use an LLM or deep NLP model.
    
    # 1. Guidance extraction
    if re.search(r'\b(guidance|outlook|expect to grow|projected)\b', text_lower):
        facts.append(ExtractedFact(
            metric="GUIDANCE_UPDATED",
            value="YES",
            period="FORWARD",
            confidence=0.85
        ))
        
    # 2. Capex extraction
    if re.search(r'\b(capex|capital expenditure|capacity expansion)\b', text_lower):
        facts.append(ExtractedFact(
            metric="CAPEX_ANNOUNCED",
            value="YES",
            period="FORWARD",
            confidence=0.80
        ))
        
    # 3. Revenue extraction (e.g. "Revenue grew 20% YoY")
    rev_match = re.search(r'revenue (?:grew|increased|up) (?:by )?(\d+(?:\.\d+)?%) (?:yoy|year-on-year)', text_lower)
    if rev_match:
        facts.append(ExtractedFact(
            metric="REVENUE_GROWTH_YOY",
            value=rev_match.group(1),
            period="CURRENT",
            confidence=0.90
        ))
        
    return facts

@app.post("/extract", response_model=DocumentResponse)
async def extract_document(req: DocumentRequest):
    temp_fd, temp_path = tempfile.mkstemp(suffix=".pdf")
    os.close(temp_fd)
    
    try:
        download_pdf(req.url, temp_path)
        
        # Fast text extraction using PyMuPDF
        full_text = ""
        doc = fitz.open(temp_path)
        for page in doc:
            full_text += page.get_text()
        doc.close()
        
        # Complex table extraction using pdfplumber could go here
        # with pdfplumber.open(temp_path) as pdf: ...
        
        facts = extract_facts_from_text(full_text)
        
        return DocumentResponse(
            symbol=req.symbol,
            facts=facts,
            raw_text_length=len(full_text)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
