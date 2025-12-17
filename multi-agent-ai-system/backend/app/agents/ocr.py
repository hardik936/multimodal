from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from app.llm.groq_client import call_groq_sync
import json
import os
import pdfplumber

class OCRState(TypedDict):
    document_text: Optional[str]
    file_path: Optional[str] # New field for file path
    invoice_number: Optional[str]
    total: Optional[str]
    final_output: Optional[str]
    workflow_id: Optional[str]

def extract_node(state: OCRState):
    """
    Extracts invoice details from the document text or file using LLM.
    """
    text = state.get("document_text", "")
    file_path = state.get("file_path")
    
    # If file_path is provided, extract text from it
    if file_path and os.path.exists(file_path):
        try:
            filename, ext = os.path.splitext(file_path)
            if ext.lower() == ".pdf":
                with pdfplumber.open(file_path) as pdf:
                    extracted_pages = []
                    for page in pdf.pages:
                        extracted_pages.append(page.extract_text() or "")
                    text = "\n".join(extracted_pages)
            else:
                # Assume text file or try to read as text
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
        except Exception as e:
            return {
                "final_output": json.dumps({"error": f"Failed to read file: {str(e)}"})
            }
    
    if not text:
        return {
             "final_output": json.dumps({"error": "No text provided or extracted from file."})
        }
    
    prompt = f"""
    You are an expert Invoice OCR system. Extract the 'invoice_number' and 'total' from the following text.
    Return ONLY a JSON object with these two keys. Do not include any markdown formatting or explanation.
    
    Hash symbol (#) in invoice number should be omitted.
    Currency symbol ($) in total should be omitted.
    
    TEXT:
    {text}
    """
    
    try:
        response = call_groq_sync(prompt, temperature=0.0)
        # clean any markdown formatting if present
        cleaned_response = response.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_response)
        
        return {
            "document_text": text, # Update state with extracted text
            "invoice_number": data.get("invoice_number"),
            "total": data.get("total"),
            "final_output": cleaned_response # Store raw JSON string as final output for matcher
        }
    except Exception as e:
        print(f"OCR Extraction Failed: {e}")
        return {
            "final_output": json.dumps({"error": str(e)})
        }

def create_ocr_graph(checkpointer=None, interrupt_before=None):
    workflow = StateGraph(OCRState)
    
    workflow.add_node("extract", extract_node)
    workflow.set_entry_point("extract")
    workflow.add_edge("extract", END)
    
    return workflow.compile(checkpointer=checkpointer, interrupt_before=interrupt_before)
