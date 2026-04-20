from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import onnxruntime as ort
from tokenizers import Tokenizer
import numpy as np
import os
from dotenv import load_dotenv

# Load the variables from the .env file
load_dotenv()

app = FastAPI(title="Phishing Detection API (ONNX & Env)")

class EmailRequest(BaseModel):
    subject: str
    body: str

# Fetch the directory from the .env file. 
# We add a fallback ("./model") just in case the .env file is missing.
MODEL_DIR = os.getenv("MODEL_DIR", "./model")

print(f"Loading ultra-light ONNX model from {MODEL_DIR}...")
try:
    if not os.path.exists(MODEL_DIR):
        raise FileNotFoundError(f"Directory '{MODEL_DIR}' missing. Please check your .env path and download the model.")
        
    tokenizer = Tokenizer.from_file(os.path.join(MODEL_DIR, "tokenizer.json"))
    tokenizer.enable_truncation(max_length=512)
    tokenizer.enable_padding(length=512)
    
    session = ort.InferenceSession(os.path.join(MODEL_DIR, "model.onnx"))
    print("Model loaded successfully!")
except Exception as e:
    print(f"CRITICAL ERROR: {e}")

def softmax(x):
    e_x = np.exp(x - np.max(x))
    return e_x / e_x.sum(axis=-1, keepdims=True)

@app.post("/predict")
async def predict_email(email: EmailRequest):
    try:
        full_text = f"{email.subject} {email.body}"
        encoded = tokenizer.encode(full_text)
        
        inputs = {
            "input_ids": np.array([encoded.ids], dtype=np.int64),
            "attention_mask": np.array([encoded.attention_mask], dtype=np.int64)
        }
        
        outputs = session.run(None, inputs)
        logits = outputs[0][0]
        probs = softmax(logits)
        
        safe_prob = float(probs[0])
        phishing_prob = float(probs[1])
        
        prediction = "PHISHING" if phishing_prob > 0.5 else "SAFE"
        confidence = max(safe_prob, phishing_prob) * 100
        
        return {
            "prediction": prediction,
            "confidence_score": round(confidence, 2),
            "details": {"safe": round(safe_prob * 100, 2), "phishing": round(phishing_prob * 100, 2)}
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
