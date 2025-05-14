import os
import json
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import the GeminiService class
try:
    from gemini_service import GeminiService

    logger.info("Successfully imported GeminiService module")
except ImportError as e:
    logger.error(f"Error importing GeminiService: {e}")
    logger.info("Using GeminiService from local paste")

# Load environment variables
load_dotenv(dotenv_path=".env")


def load_test_data(file_path="./App/services/testing_files/testing_data.json"):
    """Load test data from JSON file"""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Test data file not found: {file_path}")
        return {}
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in test data file: {file_path}")
        return {}


def print_json_response(title, response):
    """Pretty print a JSON response"""
    print(f"\n{'=' * 80}")
    print(f"TEST: {title}")
    print(f"{'=' * 80}")

    if isinstance(response, dict) and response.get('error'):
        print(f"ERROR: {response.get('error')}")
        if 'raw_response' in response:
            print(f"RAW RESPONSE: {response.get('raw_response')[:500]}...")
    else:
        try:
            print(json.dumps(response, indent=2))
        except TypeError:
            print(f"Could not format as JSON: {response}")

    print(f"{'=' * 80}\n")


def test_parse_cv(service, test_data):
    """Test CV parsing"""
    cv_text = test_data.get("cv_text", "")
    parsed = service.parse_cv(cv_text)
    print_json_response(
        "CV Parsing",
        parsed
    )


def test_generate_interview_questions(service, test_data):
    """Test interview question generation"""
    print_json_response(
        "Interview Question Generation",
        service.generate_interview_questions(
            job_description=test_data.get("job_description", ""),
            cv_data=test_data.get("cv_data", {}),
            custom_questions=test_data.get("custom_questions", []),
            personality_focus=test_data.get("personality_focus", ""),
            num_questions=5
        )
    )


def test_analyze_interview_response(service, test_data):
    """Test interview response analysis"""
    # Get the first question and response from test data
    question = test_data.get("previous_questions", [""])[0]
    response = test_data.get("previous_responses", [""])[0]

    print_json_response(
        "Interview Response Analysis",
        service.analyze_interview_response(
            question=question,
            response=response,
            expected_points=["Problem identification", "Solution implementation", "Measurable results"],
            job_description=test_data.get("job_description", "")
        )
    )


def test_generate_interview_summary(service, test_data):
    """Test interview summary generation"""
    print_json_response(
        "Interview Summary",
        service.generate_interview_summary(
            transcript=test_data.get("transcript", ""),
            job_description=test_data.get("job_description", ""),
            cv_data=test_data.get("cv_data", {})
        )
    )


def test_generate_career_advice(service, test_data):
    """Test career advice generation"""
    print_json_response(
        "Career Advice",
        service.generate_career_advice(
            cv_data=test_data.get("cv_data", {}),
            career_interests=test_data.get("career_interests", []),
            personality_traits=test_data.get("personality_traits", [])
        )
    )


def test_analyze_cv_for_job(service, test_data):
    """Test CV analysis for job fit"""
    print_json_response(
        "CV Job Fit Analysis",
        service.analyze_cv_for_job(
            cv_data=test_data.get("cv_data", {}),
            job_description=test_data.get("job_description", "")
        )
    )


def test_generate_follow_up_question(service, test_data):
    """Test follow-up question generation"""
    print_json_response(
        "Follow-up Question Generation",
        service.generate_follow_up_question(
            interview_context=test_data.get("interview_context", {}),
            previous_questions=test_data.get("previous_questions", []),
            previous_responses=test_data.get("previous_responses", []),
            job_description=test_data.get("job_description", "")
        )
    )


def main():
    """Main test function"""
    # Load test data
    test_data = load_test_data()
    if not test_data:
        logger.error("No test data available. Exiting.")
        return

    # Create GeminiService instance
    api_key = os.environ.get('GEMINI_API_KEY')

    try:
        service = GeminiService(api_key=api_key)
        logger.info("GeminiService initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize GeminiService: {e}")
        return

    # Run tests for each method
    # CV Parser
    test_parse_cv(service, test_data)

    try:
        test_generate_interview_questions(service, test_data)
    except Exception as e:
        logger.error(f"Error testing generate_interview_questions: {e}")

    try:
        test_analyze_interview_response(service, test_data)
    except Exception as e:
        logger.error(f"Error testing analyze_interview_response: {e}")

    try:
        test_generate_interview_summary(service, test_data)
    except Exception as e:
        logger.error(f"Error testing generate_interview_summary: {e}")

    try:
        test_generate_career_advice(service, test_data)
    except Exception as e:
        logger.error(f"Error testing generate_career_advice: {e}")

    try:
        test_analyze_cv_for_job(service, test_data)
    except Exception as e:
        logger.error(f"Error testing analyze_cv_for_job: {e}")

    try:
        test_generate_follow_up_question(service, test_data)
    except Exception as e:
        logger.error(f"Error testing generate_follow_up_question: {e}")


if __name__ == "__main__":
    main()
