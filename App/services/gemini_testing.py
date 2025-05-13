import pytest
from unittest.mock import Mock, patch
import json
from gemini_service import GeminiService  # Replace with actual module path


class TestGeminiService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.service = GeminiService(api_key="test-api-key")
        self.sample_cv_data = {
            "skills": ["Python", "SQL"],
            "experience": [{"role": "Developer"}],
            "education": ["Computer Science"]
        }
        self.sample_job_desc = "Looking for a Python developer with 5 years experience"
        self.sample_transcript = "Interviewer: Question? Candidate: Answer."

    def test_init_missing_api_key(self):
        with pytest.raises(ValueError):
            GeminiService(api_key=None)

    @patch.object(GeminiService, '_make_request')
    def test_parse_cv_success(self, mock_make_request):
        mock_response = {
            "personal_info": {"name": "John Doe"},
            "skills": ["Python", "Testing"],
            "experience": [],
            "education": []
        }
        mock_make_request.return_value = json.dumps(mock_response)

        result = self.service.parse_cv("Sample CV text")
        assert "personal_info" in result
        assert "skills" in result
        assert isinstance(result["skills"], list)

    @patch.object(GeminiService, '_make_request')
    def test_parse_cv_invalid_json(self, mock_make_request):
        mock_make_request.return_value = "Invalid JSON"
        result = self.service.parse_cv("Bad CV")
        assert "error" in result

    @patch.object(GeminiService, '_make_request')
    def test_generate_interview_questions(self, mock_make_request):
        mock_questions = [{
            "question_text": "Test question?",
            "question_type": "technical",
            "skill_assessed": "Python",
            "difficulty": 3
        }]
        mock_make_request.return_value = json.dumps(mock_questions)

        result = self.service.generate_interview_questions(
            job_description=self.sample_job_desc,
            cv_data=self.sample_cv_data
        )
        assert isinstance(result, list)
        assert len(result) > 0
        assert "question_text" in result[0]

    @patch.object(GeminiService, '_make_request')
    def test_analyze_interview_response(self, mock_make_request):
        mock_analysis = {
            "score": 8,
            "strengths": ["Good structure"],
            "weaknesses": ["Lacked examples"]
        }
        mock_make_request.return_value = json.dumps(mock_analysis)

        result = self.service.analyze_interview_response(
            question="Test question?",
            response="Test response"
        )
        assert "score" in result
        assert isinstance(result["strengths"], list)

    @patch.object(GeminiService, '_make_request')
    def test_generate_interview_summary(self, mock_make_request):
        mock_summary = {
            "overall_score": 75,
            "summary": "Good candidate",
            "key_strengths": ["Technical skills"]
        }
        mock_make_request.return_value = json.dumps(mock_summary)

        result = self.service.generate_interview_summary(
            transcript=self.sample_transcript
        )
        assert "overall_score" in result
        assert "summary" in result

    @patch.object(GeminiService, '_make_request')
    def test_generate_career_advice(self, mock_make_request):
        mock_advice = {
            "suitable_roles": ["Python Developer"],
            "skill_gaps": ["Cloud computing"]
        }
        mock_make_request.return_value = json.dumps(mock_advice)

        result = self.service.generate_career_advice(
            cv_data=self.sample_cv_data,
            career_interests=["Software Development"]
        )
        assert "suitable_roles" in result
        assert isinstance(result["skill_gaps"], list)

    @patch.object(GeminiService, '_make_request')
    def test_analyze_cv_for_job(self, mock_make_request):
        mock_analysis = {
            "match_score": 80,
            "matching_skills": ["Python"],
            "missing_skills": ["AWS"]
        }
        mock_make_request.return_value = json.dumps(mock_analysis)

        result = self.service.analyze_cv_for_job(
            cv_data=self.sample_cv_data,
            job_description=self.sample_job_desc
        )
        assert "match_score" in result
        assert isinstance(result["matching_skills"], list)

    @patch.object(GeminiService, '_make_request')
    def test_generate_follow_up_question(self, mock_make_request):
        mock_question = {
            "question_text": "Follow up?",
            "question_type": "technical"
        }
        mock_make_request.return_value = json.dumps(mock_question)

        result = self.service.generate_follow_up_question(
            interview_context={},
            previous_questions=["What is Python?"],
            previous_responses=["It's a language"]
        )
        assert "question_text" in result
        assert len(result["question_text"]) > 0

    @patch.object(GeminiService, '_make_request')
    def test_error_handling_invalid_json(self, mock_make_request):
        mock_make_request.return_value = "Invalid JSON"

        # Test multiple methods that should handle JSON parsing errors
        methods = [
            lambda: self.service.parse_cv(""),
            lambda: self.service.generate_interview_questions(""),
            lambda: self.service.analyze_interview_response("", ""),
            lambda: self.service.generate_career_advice({}, [])
        ]

        for method in methods:
            result = method()
            assert "error" in result or "Could not" in str(result)

    @patch.object(GeminiService, '_make_request')
    def test_api_error_handling(self, mock_make_request):
        mock_make_request.side_effect = Exception("API Error")

        with pytest.raises(Exception):
            self.service.parse_cv("CV text")