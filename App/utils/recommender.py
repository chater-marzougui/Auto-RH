"""
Recommender utility for the Automated HR system.
Handles job-candidate matching, skill gap analysis, and career path recommendations.
"""
import logging
from sqlalchemy import func, desc
from app.models import User, Job, Application, Interview, CareerRoadmap
from app import db

logger = logging.getLogger(__name__)

class RecommenderSystem:
    @staticmethod
    def recommend_jobs_for_user(user_id, limit=10):
        """
        Recommends jobs based on user's skills and career goals.
        
        Args:
            user_id: The ID of the user to recommend jobs for
            limit: Maximum number of recommendations to return
            
        Returns:
            List of recommended job objects
        """
        try:
            # Get user profile and extracted skills
            user = User.query.get(user_id)
            if not user or not user.profile_data:
                logger.warning(f"User {user_id} not found or has no profile data")
                return []
            
            # Extract user skills and preferences from profile data
            user_skills = set(user.profile_data.get('skills', []))
            preferred_roles = set(user.profile_data.get('preferred_roles', []))
            
            # Get user's career roadmap if available
            roadmap = CareerRoadmap.query.filter_by(user_id=user_id).first()
            target_roles = set()
            if roadmap and roadmap.goals:
                target_roles = set(roadmap.goals.get('target_roles', []))
            
            # Find jobs that match user skills and preferences
            matching_jobs = Job.query.filter(Job.active == True).all()
            
            # Score each job based on skill match and role match
            scored_jobs = []
            for job in matching_jobs:
                job_skills = set(job.skills_required)
                skill_match_score = len(user_skills.intersection(job_skills)) / max(len(job_skills), 1)
                
                # Role matching
                role_match = 0
                if job.title.lower() in [role.lower() for role in preferred_roles.union(target_roles)]:
                    role_match = 1
                    
                # Combined score (70% skill match, 30% role preference)
                final_score = (skill_match_score * 0.7) + (role_match * 0.3)
                
                scored_jobs.append((job, final_score))
            
            # Sort by score and return top recommendations
            scored_jobs.sort(key=lambda x: x[1], reverse=True)
            return [job for job, score in scored_jobs[:limit]]
            
        except Exception as e:
            logger.error(f"Error in job recommendation: {str(e)}")
            return []
    
    @staticmethod
    def recommend_candidates_for_job(job_id, limit=20):
        """
        Recommends candidates for a specific job based on skills match and interview scores.
        
        Args:
            job_id: The ID of the job to recommend candidates for
            limit: Maximum number of candidates to recommend
            
        Returns:
            List of recommended user objects with match scores
        """
        try:
            job = Job.query.get(job_id)
            if not job:
                logger.warning(f"Job {job_id} not found")
                return []
            
            job_skills = set(job.skills_required)
            
            # Get all users who have not already applied
            existing_applicants = db.session.query(Application.user_id).filter_by(job_id=job_id).all()
            existing_applicant_ids = [applicant[0] for applicant in existing_applicants]
            
            potential_candidates = User.query.filter(
                User.role == 'user',
                ~User.id.in_(existing_applicant_ids)
            ).all()
            
            # Score candidates based on skill match and past interview performance
            scored_candidates = []
            for candidate in potential_candidates:
                if not candidate.profile_data or 'skills' not in candidate.profile_data:
                    continue
                    
                user_skills = set(candidate.profile_data.get('skills', []))
                skill_match_score = len(user_skills.intersection(job_skills)) / max(len(job_skills), 1)
                
                # Get average interview score for similar roles
                avg_score = 0
                similar_interviews = Interview.query.filter(
                    Interview.user_id == candidate.id,
                    Interview.score.isnot(None)
                ).all()
                
                if similar_interviews:
                    scores = [interview.score for interview in similar_interviews]
                    avg_score = sum(scores) / len(scores)
                
                # Combined score (60% skill match, 40% past performance)
                final_score = (skill_match_score * 0.6) + (avg_score * 0.4)
                scored_candidates.append((candidate, final_score))
            
            # Sort by score and return top recommendations
            scored_candidates.sort(key=lambda x: x[1], reverse=True)
            return [{"candidate": user, "score": round(score * 100, 2)} 
                   for user, score in scored_candidates[:limit]]
                   
        except Exception as e:
            logger.error(f"Error in candidate recommendation: {str(e)}")
            return []
    
    @staticmethod
    def analyze_skill_gaps(user_id, job_id=None, target_role=None):
        """
        Analyzes skill gaps between user's current skills and required skills for a job or target role.
        
        Args:
            user_id: The ID of the user to analyze
            job_id: Optional - specific job ID to compare against
            target_role: Optional - target role name to compare against
            
        Returns:
            Dictionary with missing skills and recommendations
        """
        try:
            user = User.query.get(user_id)
            if not user or not user.profile_data:
                logger.warning(f"User {user_id} not found or has no profile data")
                return {"missing_skills": [], "recommendations": []}
                
            user_skills = set(user.profile_data.get('skills', []))
            
            target_skills = set()
            # If job_id is provided, get skills from that job
            if job_id:
                job = Job.query.get(job_id)
                if job:
                    target_skills = set(job.skills_required)
            
            # If target role is provided, get common skills for that role
            elif target_role:
                similar_jobs = Job.query.filter(
                    func.lower(Job.title).contains(target_role.lower())
                ).all()
                
                # Collect skills from similar roles
                all_skills = []
                for job in similar_jobs:
                    all_skills.extend(job.skills_required)
                
                # Get most common skills (appearing in at least 50% of similar jobs)
                if all_skills:
                    from collections import Counter
                    skill_counts = Counter(all_skills)
                    threshold = max(1, len(similar_jobs) * 0.5)
                    target_skills = {skill for skill, count in skill_counts.items() if count >= threshold}
            
            # Identify missing skills
            missing_skills = target_skills - user_skills
            
            # Generate recommendations based on missing skills
            recommendations = []
            for skill in missing_skills:
                recommendation = {
                    "skill": skill,
                    "courses": [],  # This would come from a courses database
                    "projects": []  # This would come from a projects database
                }
                
                # Adding placeholder recommendations
                # In a real implementation, these would come from a database or external API
                if skill.lower() in ['python', 'java', 'javascript', 'sql']:
                    recommendation["courses"] = ["Online coding bootcamp", "University extension course"]
                    recommendation["projects"] = ["Build a personal portfolio", "Contribute to open source"]
                elif 'management' in skill.lower():
                    recommendation["courses"] = ["Project Management certification", "Leadership training"]
                    recommendation["projects"] = ["Lead a team project", "Organize a community event"]
                
                recommendations.append(recommendation)
            
            return {
                "missing_skills": list(missing_skills),
                "recommendations": recommendations
            }
            
        except Exception as e:
            logger.error(f"Error in skill gap analysis: {str(e)}")
            return {"missing_skills": [], "recommendations": []}
    
    @staticmethod
    def generate_career_roadmap(user_id, target_role):
        """
        Generates a career roadmap for a user to reach a target role.
        
        Args:
            user_id: The ID of the user
            target_role: The target role/position
            
        Returns:
            Dictionary with career roadmap information
        """
        try:
            user = User.query.get(user_id)
            if not user or not user.profile_data:
                logger.warning(f"User {user_id} not found or has no profile data")
                return {}
            
            # Get current user level/experience
            current_title = user.profile_data.get('current_title', 'Entry Level')
            experience_years = user.profile_data.get('experience_years', 0)
            
            # Define career levels
            career_levels = [
                "Entry Level", 
                "Junior", 
                "Mid-Level", 
                "Senior", 
                "Lead", 
                "Manager", 
                "Director"
            ]
            
            # Determine current level
            current_level = 0
            for i, level in enumerate(career_levels):
                if level.lower() in current_title.lower():
                    current_level = i
                    break
            
            # Adjust based on years of experience
            if experience_years >= 10:
                target_level = min(6, current_level + 2)
            elif experience_years >= 5:
                target_level = min(5, current_level + 1)
            else:
                target_level = min(4, current_level + 1)
            
            # Get skill gaps
            skill_gaps = RecommenderSystem.analyze_skill_gaps(user_id, target_role=target_role)
            
            # Create roadmap
            roadmap = {
                "current_level": career_levels[current_level],
                "target_level": career_levels[target_level],
                "target_role": target_role,
                "estimated_timeline_months": (target_level - current_level) * 12,
                "skill_development": skill_gaps["missing_skills"],
                "recommended_courses": [rec["courses"][0] for rec in skill_gaps["recommendations"] if rec["courses"]],
                "recommended_projects": [rec["projects"][0] for rec in skill_gaps["recommendations"] if rec["projects"]],
                "milestones": []
            }
            
            # Generate milestones
            for i in range(current_level, target_level):
                roadmap["milestones"].append({
                    "title": f"Progress to {career_levels[i+1]}",
                    "timeline_months": (i - current_level + 1) * 12,
                    "key_skills": skill_gaps["missing_skills"][:min(3, len(skill_gaps["missing_skills"]))],
                    "success_criteria": "Complete recommended courses and projects"
                })
            
            # Store roadmap in database
            existing_roadmap = CareerRoadmap.query.filter_by(user_id=user_id).first()
            if existing_roadmap:
                existing_roadmap.goals = roadmap
                existing_roadmap.recommended_skills = skill_gaps["missing_skills"]
            else:
                new_roadmap = CareerRoadmap(
                    user_id=user_id,
                    goals=roadmap,
                    recommended_skills=skill_gaps["missing_skills"]
                )
                db.session.add(new_roadmap)
            
            db.session.commit()
            
            return roadmap
            
        except Exception as e:
            logger.error(f"Error in career roadmap generation: {str(e)}")
            return {}