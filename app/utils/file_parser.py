"""
Utility functions for handling file uploads, primarily CV parsing and processing.
"""

import os
import uuid
import fitz  # PyMuPDF
from datetime import datetime
from flask import current_app
from werkzeug.utils import secure_filename
from docx import Document
import re

class FileUploadError(Exception):
    """Custom exception for file upload errors."""
    pass

def allowed_file(filename, allowed_extensions=None):
    """Check if the file extension is allowed."""
    if allowed_extensions is None:
        allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def save_uploaded_file(file, directory=None):
    """
    Save an uploaded file with a unique filename.
    
    Args:
        file: The FileStorage object from request.files
        directory: Optional subdirectory within UPLOAD_FOLDER
        
    Returns:
        Tuple of (file_path, filename)
    """
    if not file:
        raise FileUploadError("No file provided")
    
    if not allowed_file(file.filename):
        raise FileUploadError(f"File type not allowed. Allowed types: {', '.join(current_app.config['ALLOWED_EXTENSIONS'])}")
    
    # Generate a unique filename to prevent overwriting
    original_filename = secure_filename(file.filename)
    extension = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else ''
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4().hex[:8])
    new_filename = f"{timestamp}_{unique_id}.{extension}"
    
    # Determine save directory
    if directory:
        save_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], directory)
        os.makedirs(save_dir, exist_ok=True)
    else:
        save_dir = current_app.config['UPLOAD_FOLDER']
    
    # Save the file
    file_path = os.path.join(save_dir, new_filename)
    file.save(file_path)
    
    return file_path, new_filename

def extract_text_from_pdf(file_path):
    """Extract text content from a PDF file."""
    try:
        text = ""
        with fitz.open(file_path) as doc:
            for page in doc:
                text += page.get_text()
        return text
    except Exception as e:
        current_app.logger.error(f"Error extracting text from PDF: {str(e)}")
        raise FileUploadError(f"Failed to extract text from PDF: {str(e)}")

def extract_text_from_docx(file_path):
    """Extract text content from a DOCX file."""
    try:
        doc = Document(file_path)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        return text
    except Exception as e:
        current_app.logger.error(f"Error extracting text from DOCX: {str(e)}")
        raise FileUploadError(f"Failed to extract text from DOCX: {str(e)}")

def extract_text_from_file(file_path):
    """Extract text content from a file based on its extension."""
    if file_path.lower().endswith('.pdf'):
        return extract_text_from_pdf(file_path)
    elif file_path.lower().endswith(('.docx', '.doc')):
        return extract_text_from_docx(file_path)
    elif file_path.lower().endswith('.txt'):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            current_app.logger.error(f"Error reading text file: {str(e)}")
            raise FileUploadError(f"Failed to read text file: {str(e)}")
    else:
        raise FileUploadError("Unsupported file format for text extraction")

def extract_skills_from_text(text):
    """
    Extract potential skills from CV text.
    This is a basic implementation that can be enhanced with ML/NLP.
    """
    # Common programming languages and technologies
    tech_skills = [
        'Python', 'Java', 'JavaScript', 'TypeScript', 'C++', 'C#', 'Ruby', 'PHP', 'Go', 
        'Swift', 'Kotlin', 'Rust', 'SQL', 'HTML', 'CSS', 'React', 'Angular', 'Vue', 
        'Node.js', 'Django', 'Flask', 'Spring', 'ASP.NET', 'Express', 'TensorFlow',
        'PyTorch', 'Scikit-learn', 'Docker', 'Kubernetes', 'AWS', 'Azure', 'GCP',
        'Git', 'Jenkins', 'CI/CD', 'REST API', 'GraphQL', 'MongoDB', 'PostgreSQL',
        'MySQL', 'Redis', 'Elasticsearch', 'Microservices', 'Agile', 'Scrum'
    ]
    
    # Soft skills and other professional skills
    soft_skills = [
        'Leadership', 'Communication', 'Teamwork', 'Problem Solving', 'Critical Thinking',
        'Time Management', 'Project Management', 'Analytical Skills', 'Attention to Detail',
        'Creativity', 'Adaptability', 'Interpersonal Skills', 'Customer Service',
        'Decision Making', 'Negotiation', 'Presentation', 'Research', 'Writing',
        'Mentoring', 'Conflict Resolution'
    ]
    
    found_skills = []
    
    # Look for tech skills - these often have specific capitalization or formats
    for skill in tech_skills:
        # Use word boundaries to match whole words
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found_skills.append(skill)
    
    # Look for soft skills - these may have more variations in wording
    for skill in soft_skills:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text, re.IGNORECASE):
            found_skills.append(skill)
    
    return found_skills

def extract_education_from_text(text):
    """
    Extract education information from CV text.
    Uses pattern matching for common education formats.
    """
    education = []
    
    # Common degree abbreviations and full names
    degrees = [
        'Bachelor', 'BS', 'BA', 'B.S.', 'B.A.', 'BSc', 'B.Sc.', 'Master', 'MS', 'MA', 
        'M.S.', 'M.A.', 'MSc', 'M.Sc.', 'PhD', 'Ph.D.', 'Doctorate', 'MBA', 'M.B.A.'
    ]
    
    # Pattern to find education sections (can be refined further)
    education_section = re.search(r'(?i)(education|qualifications|academic background).*(?=employment|experience|skills|$)', 
                                 text, re.DOTALL)
    
    if education_section:
        edu_text = education_section.group(0)
        
        # Look for degree patterns
        for degree in degrees:
            # Match degree pattern with surrounding context
            matches = re.finditer(rf'\b{re.escape(degree)}\b.*?(?=\n\n|\Z)', edu_text, re.IGNORECASE)
            for match in matches:
                # Extract the line containing the degree
                degree_line = match.group(0).strip()
                
                # Look for years
                years_pattern = r'(19|20)\d{2}\s*-\s*(19|20)\d{2}|((19|20)\d{2})'
                years = re.findall(years_pattern, degree_line)
                year_text = years[0][0] if years else ''
                
                # Get institution name if present
                # This is simplified and may need refinement
                institutions = re.findall(r'(?:University|College|Institute|School) of [\w\s]+|[\w\s]+ (?:University|College|Institute|School)', 
                                         degree_line, re.IGNORECASE)
                institution = institutions[0] if institutions else ''
                
                education.append({
                    'degree': degree.strip(),
                    'institution': institution.strip(),
                    'period': year_text.strip(),
                    'raw_text': degree_line.strip()
                })
    
    return education

def extract_experience_from_text(text):
    """
    Extract work experience information from CV text.
    Uses pattern matching for common job formatting.
    """
    experience = []
    
    # Pattern to find experience sections
    experience_section = re.search(r'(?i)(experience|employment|work history|professional background).*(?=education|skills|projects|$)', 
                                  text, re.DOTALL)
    
    if not experience_section:
        return experience

    exp_text = experience_section.group(0)
    
    # Split by potential job entries (can be refined)
    job_entries = re.split(r'\n\n+', exp_text)
    
    for entry in job_entries:
        if len(entry.strip()) < 10:  # Skip very short entries
            continue
            
        # Try to extract job title
        title_match = re.search(r'(?i)(senior|junior|lead|principal|software|developer|engineer|manager|director|analyst|consultant|specialist|coordinator)\s+[\w\s]+', entry)
        title = title_match.group(0) if title_match else ''
        
        # Try to extract company name
        company_match = re.search(r'(?:at|with|for)\s+([\w\s]+)', entry)
        company = company_match.group(1) if company_match else ''
        
        # Try to extract dates using simpler, sequential patterns
        date_patterns = [
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}\s*-\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}',
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*\d{4}\s*-\s*(Present|Current)',
            r'(19|20)\d{2}\s*-\s*(19|20)\d{2}',
            r'(19|20)\d{2}\s*-\s*(Present|Current)'
        ]
        dates = ''
        for pattern in date_patterns:
            dates_match = re.search(pattern, entry, re.IGNORECASE)
            if dates_match:
                dates = dates_match.group(0)
                break
        
        experience.append({
            'title': title.strip(),
            'company': company.strip(),
            'period': dates.strip(),
            'raw_text': entry.strip()
        })
    
    return experience

def parse_cv(file_path):
    """
    Parse a CV file to extract structured information.
    
    Args:
        file_path: Path to the CV file
        
    Returns:
        Dictionary with extracted information
    """
    # Extract text from file
    text = extract_text_from_file(file_path)
    
    # Extract information
    skills = extract_skills_from_text(text)
    education = extract_education_from_text(text)
    experience = extract_experience_from_text(text)
    
    # Basic contact info extraction
    email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
    email = email_match.group(0) if email_match else ''
    
    phone_match = re.search(r'\b(?:\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b', text)
    phone = phone_match.group(0) if phone_match else ''
    
    # Find name (typically at the top of the CV)
    name = ''
    first_lines = text.split('\n')[:5]  # Check first 5 lines
    for line in first_lines:
        line = line.strip()
        if line and not re.search(r'@|^\d+|resume|cv|curriculum|vitae|address|phone|email', line, re.IGNORECASE):
            name = line
            break
    
    return {
        'full_text': text,
        'name': name,
        'email': email,
        'phone': phone,
        'skills': skills,
        'education': education,
        'experience': experience
    }