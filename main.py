from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from datetime import datetime
from typing import Optional
import uvicorn

from services.pdf_processor import PDFProcessor
from services.mcq_generator import MCQGenerator
from services.pdf_creator import PDFCreator
from models.schemas import MCQRequest, MCQResponse

app = FastAPI(
    title="MCQ Generator API",
    description="Generate Multiple Choice Questions from PDF documents or topics using Groq API",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize services
pdf_processor = PDFProcessor()
mcq_generator = MCQGenerator()
pdf_creator = PDFCreator()

# Create necessary directories
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)
os.makedirs("static", exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main HTML interface"""
    with open("static/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.post("/generate-from-pdf", response_model=MCQResponse)
async def generate_mcq_from_pdf(
    file: UploadFile = File(...),
    num_questions: int = Form(5),
    difficulty: str = Form("medium")
):
    """Generate MCQs from uploaded PDF file"""

    file_path = None

    try:
        print("\n" + "=" * 60)
        print("[DEBUG] /generate-from-pdf started")
        print("=" * 60)

        # --------------------------------------------------
        # 1. Validate file
        # --------------------------------------------------

        print(f"[DEBUG] File name: {file.filename}")
        print(f"[DEBUG] Number of questions: {num_questions}")
        print(f"[DEBUG] Difficulty: {difficulty}")

        if not file.filename:
            raise HTTPException(
                status_code=400,
                detail="No file was provided"
            )

        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )

        # --------------------------------------------------
        # 2. Save uploaded PDF
        # --------------------------------------------------

        os.makedirs("uploads", exist_ok=True)

        file_path = os.path.join(
            "uploads",
            file.filename
        )

        print(f"[DEBUG] Saving PDF to: {file_path}")

        content = await file.read()

        if not content:
            raise HTTPException(
                status_code=400,
                detail="Uploaded PDF is empty"
            )

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        print(f"[DEBUG] PDF saved successfully")
        print(f"[DEBUG] PDF size: {len(content)} bytes")

        # --------------------------------------------------
        # 3. Extract PDF text
        # --------------------------------------------------

        print("[DEBUG] Extracting text from PDF...")

        text_content = pdf_processor.extract_text(file_path)

        print(
            f"[DEBUG] Extracted text length: "
            f"{len(text_content) if text_content else 0}"
        )

        if not text_content or not text_content.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from PDF"
            )

        # --------------------------------------------------
        # 4. Generate MCQs using Groq
        # --------------------------------------------------

        print("[DEBUG] Sending text to MCQ generator...")

        mcqs = await mcq_generator.generate_from_text(
            text_content,
            num_questions,
            difficulty
        )

        print(
            f"[DEBUG] MCQ generation completed. "
            f"Generated: {len(mcqs)} questions"
        )

        # --------------------------------------------------
        # 5. Create output PDF
        # --------------------------------------------------

        os.makedirs("outputs", exist_ok=True)

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        output_filename = f"mcq_output_{timestamp}.pdf"

        output_path = os.path.join(
            "outputs",
            output_filename
        )

        print(f"[DEBUG] Creating output PDF: {output_path}")

        pdf_creator.create_mcq_pdf(
            mcqs,
            output_path,
            source=f"PDF: {file.filename}"
        )

        print("[DEBUG] Output PDF created successfully")

        # --------------------------------------------------
        # 6. Remove uploaded PDF
        # --------------------------------------------------

        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            print("[DEBUG] Temporary uploaded PDF removed")

        # --------------------------------------------------
        # 7. Return response
        # --------------------------------------------------

        response = MCQResponse(
            questions=mcqs,
            download_url=f"/download/{output_filename}",
            total_questions=len(mcqs)
        )

        print("[DEBUG] Request completed successfully")
        print("=" * 60)

        return response

    except HTTPException:
        # Keep our intentional HTTP errors
        raise

    except Exception as e:
        import traceback

        print("\n" + "=" * 60)
        print("[ERROR] /generate-from-pdf FAILED")
        print("=" * 60)
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print("\nFULL TRACEBACK:")
        traceback.print_exc()
        print("=" * 60)

        # Clean up uploaded file if something failed
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                print("[DEBUG] Temporary PDF removed after error")
            except Exception:
                pass

        raise HTTPException(
            status_code=500,
            detail=f"{type(e).__name__}: {str(e)}"
        )
        
@app.post("/generate-from-topic", response_model=MCQResponse)
async def generate_mcq_from_topic(request: MCQRequest):
    """Generate MCQs from a given topic"""
    try:
        # Generate MCQs
        mcqs = await mcq_generator.generate_from_topic(
            request.topic,
            request.num_questions,
            request.difficulty,
            request.subtopics
        )
        
        # Create output PDF
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"mcq_topic_{timestamp}.pdf"
        output_path = f"outputs/{output_filename}"
        
        pdf_creator.create_mcq_pdf(mcqs, output_path, source=f"Topic: {request.topic}")
        
        return MCQResponse(
            questions=mcqs,
            download_url=f"/download/{output_filename}",
            total_questions=len(mcqs)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/download/{filename}")
async def download_file(filename: str):
    """Download generated PDF file"""
    file_path = f"outputs/{filename}"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=filename
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)