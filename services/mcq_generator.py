import os
import json
import asyncio
from groq import AsyncGroq
from typing import List, Optional
from models.schemas import MCQQuestion

class MCQGenerator:
    def __init__(self):
        self.client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")  # You can change this to other Groq models
    
    async def generate_from_text(self, text: str, num_questions: int = 5, difficulty: str = "medium") -> List[MCQQuestion]:
        """Generate MCQs from provided text content"""
        
        prompt = self._create_text_prompt(text, num_questions, difficulty)
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert educator who creates high-quality multiple choice questions. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=4000
            )
            
            mcqs_data = json.loads(response.choices[0].message.content)
            return [MCQQuestion(**mcq) for mcq in mcqs_data["questions"]]
            
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            content = response.choices[0].message.content
            return self._parse_fallback_response(content)
        except Exception as e:
            raise Exception(f"Error generating MCQs: {str(e)}")
    
    async def generate_from_topic(self, topic: str, num_questions: int = 5, difficulty: str = "medium", subtopics: Optional[List[str]] = None) -> List[MCQQuestion]:
        """Generate MCQs from a given topic"""
        
        prompt = self._create_topic_prompt(topic, num_questions, difficulty, subtopics)
        
        try:
            response = await self.client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "You are an expert educator who creates high-quality multiple choice questions. Always respond with valid JSON format."},
                    {"role": "user", "content": prompt}
                ],
                model=self.model,
                temperature=0.7,
                max_tokens=4000
            )
            
            mcqs_data = json.loads(response.choices[0].message.content)
            return [MCQQuestion(**mcq) for mcq in mcqs_data["questions"]]
            
        except json.JSONDecodeError:
            # Fallback: try to extract JSON from response
            content = response.choices[0].message.content
            return self._parse_fallback_response(content)
        except Exception as e:
            raise Exception(f"Error generating MCQs: {str(e)}")
    
    def _create_text_prompt(self, text: str, num_questions: int, difficulty: str) -> str:
        """Create prompt for text-based MCQ generation"""
        return f"""
Based on the following text content, create {num_questions} multiple choice questions at {difficulty} difficulty level.

TEXT CONTENT:
{text[:3000]}  # Limit text to avoid token limits

REQUIREMENTS:
- Create exactly {num_questions} questions
- Each question should have exactly 4 options (A, B, C, D)
- Questions should be at {difficulty} difficulty level
- Include explanations for correct answers
- Cover different aspects of the content
- Questions should be clear and unambiguous

RESPONSE FORMAT (JSON):
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
      "correct_answer": "A) Option 1",
      "explanation": "Explanation of why this is correct"
    }}
  ]
}}

Generate the MCQs now:
"""
    
    def _create_topic_prompt(self, topic: str, num_questions: int, difficulty: str, subtopics: Optional[List[str]]) -> str:
        """Create prompt for topic-based MCQ generation"""
        subtopics_text = ""
        if subtopics:
            subtopics_text = f"\nFocus on these subtopics: {', '.join(subtopics)}"
            
        return f"""
Create {num_questions} multiple choice questions about: {topic}
{subtopics_text}

REQUIREMENTS:
- Create exactly {num_questions} questions
- Each question should have exactly 4 options (A, B, C, D)
- Questions should be at {difficulty} difficulty level
- Include explanations for correct answers
- Cover different aspects of the topic
- Questions should be clear and unambiguous
- Make sure only one option is clearly correct

DIFFICULTY GUIDELINES:
- Easy: Basic concepts, definitions, simple recall
- Medium: Application of concepts, analysis, moderate complexity
- Hard: Advanced concepts, critical thinking, complex scenarios

RESPONSE FORMAT (JSON):
{{
  "questions": [
    {{
      "question": "Question text here?",
      "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"],
      "correct_answer": "A) Option 1",
      "explanation": "Explanation of why this is correct"
    }}
  ]
}}

Generate the MCQs now:
"""
    
    def _parse_fallback_response(self, content: str) -> List[MCQQuestion]:
        """Fallback parser for non-JSON responses"""
        # This is a simple fallback - you might want to implement more robust parsing
        try:
            # Try to find JSON in the response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                mcqs_data = json.loads(json_str)
                return [MCQQuestion(**mcq) for mcq in mcqs_data["questions"]]
        except:
            pass
        
        # If all else fails, return a simple error question
        return [MCQQuestion(
            question="Error generating question. Please try again.",
            options=["A) Error", "B) Error", "C) Error", "D) Error"],
            correct_answer="A) Error",
            explanation="There was an error generating this question."
        )]