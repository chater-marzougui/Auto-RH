"""
Gemini Service - Handles interactions with Google's Gemini AI API

This module provides functions to interact with the Gemini API for:
- Interview question generation
- CV parsing and skill extraction
- Response analysis and scoring
- Career advice generation
"""
import os
import json
from flask import current_app
import google.generativeai as genai
from typing import Dict, List, Tuple, Any, Optional


class GeminiService:
    def __init__(self, api_key=None):
        """Initialize the Gemini service with API key."""
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY') or current_app.config.get('GEMINI_API_KEY')

        if not self.api_key:
            raise ValueError("Gemini API key not provided and not found in environment or app config")

    def _make_request(self, prompt: str, parameters: Dict = None, system_prompt: str = "") -> str:
        """Make a request to the Gemini API.
        
        Args:
            prompt: The prompt to send to Gemini
            parameters: Optional parameters for the request (temperature, etc.)
            
        Returns:
            The JSON response from the API
        """
        if parameters is None:
            parameters = {
                "temperature": 0.7,
                "top_p": 0.8,
                "top_k": 40,
                "max_output_tokens": 8192,
            }

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash-exp",
            generation_config=parameters,
            system_instruction=system_prompt,
        )
        chat_session = model.start_chat(history=[])
        response = chat_session.send_message(prompt).text

        return response

    def parse_cv(self, cv_text: str) -> Dict:
        """Extract skills, experiences, and qualifications from a CV.
        
        Args:
            cv_text: The text content of the CV
            
        Returns:
            Dictionary containing parsed CV information
        """
        system_prompt = "You are a highly skilled HR professional with expertise in CV parsing and analysis."

        prompt = f"""
        Analyze the following CV and extract key information in JSON format:
        
        CV Text:
        {cv_text}
        
        Please extract and return a JSON object with the following fields:
        1. personal_info: Name, contact details, location
        2. skills: List of technical and soft skills
        3. experience: List of work experiences with company, role, duration, and key achievements
        4. education: Academic background
        5. projects: Personal or professional projects
        6. certifications: Professional certifications
        7. languages: Languages spoken and proficiency levels
        8. keywords: Important keywords that highlight expertise
        9. years_of_experience: Total years of relevant experience
        
        Return ONLY the JSON object without any additional text.
        """

        # Use stricter parameters for CV parsing to ensure accuracy
        parameters = {
            "temperature": 0.2,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
            "response_mime_type": "response_mime_type"
        }

        response = self._make_request(system_prompt+prompt, parameters)
        try:
            return json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing CV response: {e}")
            return {
                "error": "Failed to parse CV",
                "raw_response": str(response)
            }

    def generate_interview_questions(self, job_description: str, cv_data: Dict = None,
                                     custom_questions: List[str] = None,
                                     personality_focus: str = None,
                                     num_questions: int = 10) -> List[Dict]:
        """Generate interview questions based on job description and CV.
        
        Args:
            job_description: The job description text
            cv_data: Optional dictionary containing parsed CV data
            custom_questions: Optional list of must-ask questions
            personality_focus: Optional personality traits to focus on
            num_questions: Number of questions to generate
            
        Returns:
            List of question dictionaries with metadata
        """
        # Create the prompt for Gemini
        prompt_parts = [
            f"Generate {num_questions} interview questions for the following job description:",
            f"\nJOB DESCRIPTION:\n{job_description}\n"
        ]

        if cv_data:
            cv_json = json.dumps(cv_data, indent=2)
            prompt_parts.append(f"\nCANDIDATE CV DATA:\n{cv_json}\n")
            prompt_parts.append("Tailor some questions to verify the candidate's claimed skills and experience.")

        if custom_questions:
            questions_text = "\n".join([f"- {q}" for q in custom_questions])
            prompt_parts.append(f"\nMUST-ASK QUESTIONS:\n{questions_text}\n")
            prompt_parts.append("Include these questions in your output.")

        if personality_focus:
            prompt_parts.append(f"\nPERSONALITY FOCUS:\n{personality_focus}\n")
            prompt_parts.append("Include questions that assess these personality traits.")

        prompt_parts.append("""
        Return the questions as a JSON array where each question is an object with:
        1. "question_text": The actual question
        2. "question_type": Either "technical", "behavioral", "experience", or "custom"
        3. "skill_assessed": The primary skill or trait being assessed
        4. "difficulty": A rating from 1-5 where 5 is most difficult
        5. "expected_answer_points": Key points a good answer should cover
        
        Return ONLY the JSON array without any additional text.
        """)

        prompt = "\n".join(prompt_parts)

        parameters = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }

        response = self._make_request(prompt, parameters)

        try:
            return json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing questions response: {e}")
            return [{"question_text": "Could not generate questions. Please try again.",
                     "error": str(e)}]

    def analyze_interview_response(self, question: str, response: str,
                                   expected_points: List[str] = None,
                                   job_description: str = None) -> Dict:
        """Analyze a candidate's response to an interview question.
        
        Args:
            question: The interview question
            response: The candidate's response
            expected_points: Optional list of points a good answer should cover
            job_description: Optional job description for context
            
        Returns:
            Dictionary with analysis results
        """
        prompt_parts = [
            "Analyze the following interview response:",
            f"\nQUESTION:\n{question}\n",
            f"\nCANDIDATE RESPONSE:\n{response}\n",
        ]

        if expected_points:
            points_text = "\n".join([f"- {p}" for p in expected_points])
            prompt_parts.append(f"\nEXPECTED ANSWER POINTS:\n{points_text}\n")

        if job_description:
            prompt_parts.append(f"\nJOB DESCRIPTION CONTEXT:\n{job_description}\n")

        prompt_parts.append("""
        Analyze the response and return a JSON object with:
        1. "score": Numerical score from 1-10
        2. "strengths": List of response strengths
        3. "weaknesses": List of response weaknesses
        4. "technical_accuracy": Assessment of technical accuracy from 1-10 (if applicable)
        5. "communication_clarity": Assessment of communication clarity from 1-10
        6. "completeness": Assessment of how completely the question was answered from 1-10
        7. "improvement_suggestions": Specific suggestions for improvement
        8. "keywords_mentioned": Important keywords mentioned in the response
        9. "expected_points_covered": Percentage of expected points covered (if provided)
        
        Return ONLY the JSON object without any additional text.
        """)

        prompt = "\n".join(prompt_parts)

        parameters = {
            "temperature": 0.3,  # Lower temperature for more consistent scoring
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        response = self._make_request(prompt, parameters)

        try:
            return json.loads(response)

        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing analysis response: {e}")
            return {
                "score": 5,
                "error": "Failed to analyze response",
                "raw_response": response
            }

    def generate_interview_summary(self, transcript: str, job_description: str = None,
                                   cv_data: Dict = None) -> Dict:
        """Generate a summary and overall assessment of an interview.
        
        Args:
            transcript: The full interview transcript
            job_description: Optional job description
            cv_data: Optional CV data
            
        Returns:
            Dictionary with interview assessment and recommendations
        """
        prompt_parts = [
            "Generate a comprehensive assessment of the following job interview:",
            f"\nINTERVIEW TRANSCRIPT:\n{transcript}\n",
        ]

        if job_description:
            prompt_parts.append(f"\nJOB DESCRIPTION:\n{job_description}\n")

        if cv_data:
            cv_summary = json.dumps({k: cv_data[k] for k in ['skills', 'experience', 'education']
                                     if k in cv_data}, indent=2)
            prompt_parts.append(f"\nCANDIDATE BACKGROUND:\n{cv_summary}\n")

        prompt_parts.append("""
        Provide a detailed assessment in JSON format with:
        1. "overall_score": Numerical score from 1-100
        2. "technical_score": Technical knowledge score from 1-100
        3. "soft_skills_score": Soft skills score from 1-100
        4. "key_strengths": List of candidate's key strengths (max 5)
        5. "areas_for_improvement": List of areas for improvement (max 5)
        6. "job_fit_assessment": Assessment of how well the candidate fits the job
        7. "recommended_next_steps": Recommendations for next steps
        8. "summary": Brief summary of the interview (max 250 words)
        9. "standout_moments": Notable moments from the interview
        10. "hiring_recommendation": "Strong Yes", "Yes", "Maybe", "No", or "Strong No"
        
        Return ONLY the JSON object without any additional text.
        """)

        prompt = "\n".join(prompt_parts)

        parameters = {
            "temperature": 0.4,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }

        response = self._make_request(prompt, parameters)

        try:
            json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing summary response: {e}")
            return {
                "overall_score": 50,
                "summary": "Could not generate interview summary due to an error.",
                "error": str(e)
            }

    def generate_career_advice(self, cv_data: Dict, career_interests: List[str],
                               personality_traits: List[str] = None) -> Dict:
        """Generate career advice and roadmap based on CV and interests.
        
        Args:
            cv_data: Dictionary containing parsed CV data
            career_interests: List of career interests/goals
            personality_traits: Optional list of personality traits
            
        Returns:
            Dictionary with career advice and roadmap
        """
        cv_json = json.dumps(cv_data, indent=2)
        interests_text = ", ".join(career_interests)

        prompt_parts = [
            "Generate personalized career advice and a roadmap based on the following information:",
            f"\nCV DATA:\n{cv_json}\n",
            f"\nCAREER INTERESTS/GOALS:\n{interests_text}\n",
        ]

        if personality_traits:
            traits_text = ", ".join(personality_traits)
            prompt_parts.append(f"\nPERSONALITY TRAITS:\n{traits_text}\n")

        prompt_parts.append("""
        Provide career advice in JSON format with:
        1. "suitable_roles": List of 3-5 suitable roles with brief explanations of fit
        2. "skill_gaps": Skills the person should develop for their desired roles
        3. "recommended_courses": 3-5 specific courses or certifications to pursue
        4. "recommended_projects": 3-5 project ideas to build relevant experience
        5. "career_roadmap": A 1-3 year roadmap with specific milestones and goals
        6. "networking_advice": Specific networking strategies for their field
        7. "resume_improvement_tips": Specific ways to improve their CV for target roles
        8. "interview_preparation": Key areas to focus on for interviews in target roles
        9. "career_growth_potential": Assessment of long-term growth in chosen paths
        
        Return ONLY the JSON object without any additional text.
        """)

        prompt = "\n".join(prompt_parts)

        parameters = {
            "temperature": 0.6,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 4096,
        }

        response = self._make_request(prompt, parameters)

        try:
            return json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing career advice response: {e}")
            return {
                "error": "Failed to generate career advice",
                "raw_response": response
            }

    def analyze_cv_for_job(self, cv_data: Dict, job_description: str) -> Dict:
        """Analyze a CV against a specific job description to determine fit.
        
        Args:
            cv_data: Dictionary containing parsed CV data
            job_description: The job description text
            
        Returns:
            Dictionary with analysis results
        """
        cv_json = json.dumps(cv_data, indent=2)

        prompt = f"""
        Analyze how well the following CV matches the job description:
        
        JOB DESCRIPTION:
        {job_description}
        
        CV DATA:
        {cv_json}
        
        Return a detailed analysis in JSON format with:
        1. "match_score": Overall match score from 0-100
        2. "matching_skills": Skills from the CV that match the job requirements
        3. "missing_skills": Skills required by the job that aren't in the CV
        4. "experience_relevance": How relevant the candidate's experience is (0-100)
        5. "education_relevance": How relevant the candidate's education is (0-100)
        6. "strengths": Areas where the candidate is strong for this role
        7. "weaknesses": Areas where the candidate may fall short
        8. "recommendation": Whether to interview the candidate ("Highly Recommend", "Recommend", "Maybe", "Not Recommended")
        9. "improvement_suggestions": Specific suggestions for how the candidate could improve their fit
        
        Return ONLY the JSON object without any additional text.
        """

        parameters = {
            "temperature": 0.3,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 2048,
        }

        response = self._make_request(prompt, parameters)

        try:
            return json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing CV job analysis response: {e}")
            return {
                "match_score": 50,
                "error": "Failed to analyze CV for job fit",
                "raw_response": str(response)
            }

    def generate_follow_up_question(self, interview_context: Dict,
                                    previous_questions: List[str],
                                    previous_responses: List[str],
                                    job_description: str = None) -> Dict:
        """Generate a dynamic follow-up question based on the interview context.
        
        Args:
            interview_context: Information about the interview
            previous_questions: List of previous questions
            previous_responses: List of previous responses
            job_description: Optional job description for context
            
        Returns:
            Dictionary with the follow-up question and metadata
        """
        # Create a history of Q&A for context
        qa_history = []
        for i in range(min(len(previous_questions), len(previous_responses))):
            qa_history.append(f"Q: {previous_questions[i]}")
            qa_history.append(f"A: {previous_responses[i]}")
        qa_history_text = "\n".join(qa_history)

        context_json = json.dumps(interview_context, indent=2)

        prompt_parts = [
            "Generate a relevant follow-up interview question based on the conversation history:",
            f"\nINTERVIEW CONTEXT:\n{context_json}\n",
            f"\nCONVERSATION HISTORY:\n{qa_history_text}\n",
        ]

        if job_description:
            prompt_parts.append(f"\nJOB DESCRIPTION:\n{job_description}\n")

        prompt_parts.append("""
        Based on the previous questions and answers, generate a follow-up question that:
        1. Probes deeper into an area where the candidate's response was insufficient
        2. Explores a new relevant area based on their previous answers
        3. Clarifies any potential inconsistencies or vague points
        
        Return the question as a JSON object with:
        1. "question_text": The actual follow-up question
        2. "question_type": The type of question (technical, behavioral, etc.)
        3. "purpose": The purpose of asking this follow-up
        4. "related_to_previous_question": Index of the previous question this follows up on (0-based)
        5. "expected_answer_points": Key points a good answer should cover
        
        Return ONLY the JSON object without any additional text.
        """)

        prompt = "\n".join(prompt_parts)

        parameters = {
            "temperature": 0.7,
            "top_p": 0.95,
            "top_k": 40,
            "max_output_tokens": 1024,
        }

        response = self._make_request(prompt, parameters)

        try:
            return json.loads(response)
        except (KeyError, json.JSONDecodeError) as e:
            current_app.logger.error(f"Error parsing follow-up question response: {e}")
            return {
                "question_text": "Can you elaborate more on your previous answer?",
                "question_type": "general",
                "error": str(e)
            }
