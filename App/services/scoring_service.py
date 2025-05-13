"""
Scoring Service for Automated HR
Handles all interview scoring logic and assessment processing
"""
import logging
from typing import Dict, List, Tuple, Optional
import json
from app.models import Interview, User, Job
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)

class ScoringService:
    """
    Service to handle interview scoring and evaluation
    """
    def __init__(self, gemini_service: Optional[GeminiService] = None):
        self.gemini_service = gemini_service or GeminiService()
        
        # Scoring categories and their weights
        self.scoring_categories = {
            'technical_skills': 0.35,
            'communication': 0.20,
            'problem_solving': 0.25,
            'experience_relevance': 0.15,
            'cultural_fit': 0.05
        }
        
    def score_interview(self, interview_id: int, custom_weights: Dict[str, float] = None) -> Dict:
        """
        Score an interview based on the transcript and answers
        
        Args:
            interview_id: ID of the interview to score
            custom_weights: Optional custom category weights provided by the enterprise
            
        Returns:
            Dict containing scores and assessment details
        """
        try:
            # Get interview data
            interview = Interview.query.get_or_404(interview_id)
            transcript = interview.transcript
            job = Job.query.get(interview.job_id) if interview.job_id else None
            # user = User.query.get(interview.user_id)"""
            
            # Use custom weights if provided
            weights = custom_weights or self.scoring_categories
            
            # Process transcript through Gemini for comprehensive scoring
            scoring_prompt = self._create_scoring_prompt(transcript, job, weights)
            scoring_result = self.gemini_service.generate_response(scoring_prompt)
            
            try:
                # Parse the JSON response from Gemini
                scores = json.loads(scoring_result)
            except json.JSONDecodeError:
                # If Gemini doesn't return valid JSON, apply fallback scoring method
                logger.warning(f"Failed to parse Gemini scoring response for interview {interview_id}")
                scores = self._fallback_scoring(transcript, weights)
            
            # Calculate weighted final score
            final_score = self._calculate_final_score(scores)
            
            # Store the calculated scores
            self._save_scores(interview, scores, final_score)
            
            return {
                'interview_id': interview_id,
                'overall_score': final_score,
                'category_scores': scores,
                'assessment_summary': scores.get('summary', ''),
                'improvement_tips': scores.get('improvement_tips', [])
            }
            
        except Exception as e:
            logger.error(f"Error scoring interview {interview_id}: {str(e)}")
            return {
                'interview_id': interview_id,
                'error': f"Failed to score interview: {str(e)}",
                'overall_score': 0
            }
    
    def _create_scoring_prompt(self, transcript: str, job: Job, weights: Dict[str, float]) -> str:
        """
        Create a prompt for Gemini to score the interview
        
        Args:
            transcript: The interview transcript
            job: The job being applied for
            user: The user/candidate
            weights: Scoring category weights
            
        Returns:
            Structured prompt for Gemini API
        """
        job_description = job.description if job else "Not specified"
        job_title = job.title if job else "General Interview"
        
        prompt = f"""
        You are an expert HR assessment AI. Your task is to evaluate an interview for the position of {job_title}.
        
        JOB DESCRIPTION:
        {job_description}
        
        INTERVIEW TRANSCRIPT:
        {transcript}
        
        EVALUATION INSTRUCTIONS:
        1. Score each category on a scale of 0-100:
           - Technical Skills (weight: {weights['technical_skills']})
           - Communication (weight: {weights['communication']})
           - Problem Solving (weight: {weights['problem_solving']})
           - Experience Relevance (weight: {weights['experience_relevance']})
           - Cultural Fit (weight: {weights['cultural_fit']})
        
        2. Provide a short assessment summary (2-3 paragraphs)
        3. List 3-5 specific improvement suggestions for the candidate
        
        RESPOND WITH A JSON OBJECT WITH THE FOLLOWING STRUCTURE:
        {{
            "technical_skills": <score>,
            "communication": <score>,
            "problem_solving": <score>,
            "experience_relevance": <score>,
            "cultural_fit": <score>,
            "summary": "<assessment summary>",
            "improvement_tips": ["tip1", "tip2", "tip3"]
        }}
        """
        return prompt
    
    def _fallback_scoring(self, transcript: str, weights: Dict[str, float]) -> Dict:
        """
        Fallback scoring method if Gemini API fails
        Implements basic keyword and phrase analysis
        
        Args:
            transcript: The interview transcript
            weights: Scoring category weights
            
        Returns:
            Dict with calculated scores
        """
        # A very basic scoring approach based on keywords and length
        scores = {}
        
        # Default empty transcript handling
        if not transcript or transcript.strip() == "":
            return {
                category: 0 for category in weights.keys()
            }
        
        # Simple length-based estimation (longer, more detailed answers are generally better)
        word_count = len(transcript.split())
        base_score = min(70, max(40, word_count // 20))  # Map to a 40-70 score range
        
        # Apply small random variations for each category to avoid identical scores
        import random
        for category in weights.keys():
            variation = random.randint(-5, 5)
            scores[category] = min(100, max(0, base_score + variation))
        
        return {
            **scores,
            'summary': "Automated fallback scoring was applied due to processing issues.",
            'improvement_tips': [
                "Provide more detailed responses to questions",
                "Focus on concrete examples from your experience",
                "Align your answers with the job requirements"
            ]
        }
    
    def _calculate_final_score(self, scores: Dict) -> float:
        """
        Calculate the final weighted score
        
        Args:
            scores: Dict of category scores
            
        Returns:
            Weighted final score (0-100)
        """
        final_score = 0
        for category, weight in self.scoring_categories.items():
            if category in scores:
                final_score += scores[category] * weight
        
        return round(final_score, 1)
    
    def _save_scores(self, interview: Interview, scores: Dict, final_score: float) -> None:
        """
        Save the scores to the interview record
        
        Args:
            interview: Interview model instance
            scores: Dict containing category scores
            final_score: Calculated final score
        """
        interview.score = final_score
        interview.score_breakdown = json.dumps(scores)
        
        # Generate summary if not present in scores
        if 'summary' not in scores or not scores['summary']:
            summary = f"Overall score: {final_score}/100. "
            summary += "Performance was " 
            if final_score >= 85:
                summary += "excellent."
            elif final_score >= 70:
                summary += "good."
            elif final_score >= 50:
                summary += "satisfactory."
            else:
                summary += "below expectations."
            interview.summary = summary
        else:
            interview.summary = scores['summary']
            
        from app import db
        db.session.commit()
    
    def get_comparison_stats(self, job_id: int) -> Dict:
        """
        Get comparative statistics for a job's interviews
        
        Args:
            job_id: ID of the job
            
        Returns:
            Dict with statistical information
        """
        interviews = Interview.query.filter_by(job_id=job_id).all()
        
        if not interviews:
            return {
                'count': 0,
                'average_score': 0,
                'highest_score': 0,
                'percentiles': {}
            }
        
        scores = [i.score for i in interviews if i.score is not None]
        
        if not scores:
            return {
                'count': len(interviews),
                'average_score': 0,
                'highest_score': 0,
                'percentiles': {}
            }
            
        scores.sort()
        
        return {
            'count': len(scores),
            'average_score': sum(scores) / len(scores),
            'highest_score': max(scores),
            'percentiles': {
                '25': scores[int(len(scores) * 0.25)] if len(scores) >= 4 else 0,
                '50': scores[int(len(scores) * 0.5)] if len(scores) >= 2 else 0,
                '75': scores[int(len(scores) * 0.75)] if len(scores) >= 4 else 0,
                '90': scores[int(len(scores) * 0.9)] if len(scores) >= 10 else 0,
            }
        }
        
    def generate_feedback_report(self, interview_id: int) -> Dict:
        """
        Generate a detailed feedback report for an interview
        
        Args:
            interview_id: ID of the interview
            
        Returns:
            Dict containing the detailed feedback
        """
        interview = Interview.query.get_or_404(interview_id)
        
        # If we don't have scores yet, generate them
        if not interview.score:
            self.score_interview(interview_id)
            interview = Interview.query.get(interview_id)  # Refresh
            
        # Get score breakdown
        try:
            scores = json.loads(interview.score_breakdown) if interview.score_breakdown else {}
        except json.JSONDecodeError:
            scores = {}
            
        # Generate detailed feedback using Gemini if needed
        if not scores.get('detailed_feedback'):
            feedback_prompt = f"""
            You are an expert HR coach. Review this interview transcript and provide detailed, actionable feedback:
            
            TRANSCRIPT:
            {interview.transcript}
            
            CURRENT ASSESSMENT:
            {interview.summary}
            
            Provide detailed feedback with:
            1. Strengths (3-5 points)
            2. Areas for improvement (3-5 points)
            3. Specific actionable advice
            
            RESPOND WITH JSON:
            {{
                "strengths": ["point1", "point2", "point3"],
                "improvement_areas": ["area1", "area2", "area3"],
                "actionable_advice": ["advice1", "advice2", "advice3"]
            }}
            """
            
            try:
                feedback_result = self.gemini_service.generate_response(feedback_prompt)
                detailed_feedback = json.loads(feedback_result)
            except Exception as e:
                logger.error(f"Error generating detailed feedback: {str(e)}")
                detailed_feedback = {
                    "strengths": ["Unable to analyze strengths at this time"],
                    "improvement_areas": ["Unable to analyze improvement areas at this time"],
                    "actionable_advice": ["Please try again later for detailed feedback"]
                }
        else:
            detailed_feedback = scores.get('detailed_feedback')
            
        # Get comparative stats if this is for a specific job
        comparative_stats = None
        if interview.job_id:
            comparative_stats = self.get_comparison_stats(interview.job_id)
            
        return {
            'interview_id': interview_id,
            'score': interview.score,
            'category_scores': scores,
            'summary': interview.summary,
            'detailed_feedback': detailed_feedback,
            'comparative_stats': comparative_stats
        }