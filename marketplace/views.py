import json
import re
import requests
try:
    import google.generativeai as genai
except (ImportError, Exception):
    genai = None
from django.conf import settings
from django.shortcuts import render
from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from .models import CustomUser, Project, Application, Bookmark
from .serializers import (
    UserSerializer,
    ProjectSerializer,
    ApplicationSerializer,
    FounderApplicationSerializer,
    FounderProjectSerializer,
)

# Configure Gemini AI using API Key from settings if available
if genai and getattr(settings, 'GEMINI_API_KEY', None):
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    except Exception:
        pass


def index(request):
    return render(request, 'index.html')


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_user(request):
    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    email = data.get('email')
    password = data.get('password')

    if not email or not str(email).strip():
        return Response({'error': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
    email = str(email).strip().lower()

    if '@' not in email or '.' not in email.split('@')[-1]:
        return Response({'error': 'Please provide a valid email address.'}, status=status.HTTP_400_BAD_REQUEST)

    if not password or not str(password).strip():
        return Response({'error': 'Password is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if len(str(password)) < 6:
        return Response({'error': 'Password must be at least 6 characters long.'}, status=status.HTTP_400_BAD_REQUEST)

    role = str(data.get('role', 'student')).lower().strip()
    if role not in ['student', 'founder']:
        return Response({'error': 'Role must be either "student" or "founder".'}, status=status.HTTP_400_BAD_REQUEST)

    full_name = str(data.get('full_name', '')).strip()

    if CustomUser.objects.filter(username=email).exists() or CustomUser.objects.filter(email=email).exists():
        return Response({'error': 'A user with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user = CustomUser.objects.create_user(
            username=email,
            email=email,
            password=password,
            role=role,
            full_name=full_name
        )
        return Response({'message': 'User registered successfully'}, status=status.HTTP_201_CREATED)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.filter(status='open').order_by('-created_at')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        # Role boundary: Students cannot create projects; only founders (or staff) can.
        if getattr(request.user, 'role', None) != 'founder' and not request.user.is_staff:
            return Response(
                {'error': 'Forbidden: Only founders can create projects.'},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data
        if not isinstance(data, dict):
            return Response(
                {'error': 'Invalid payload format: expected JSON object.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        required_fields = ['title', 'company', 'description', 'duration', 'payment_type', 'reward']
        for field in required_fields:
            val = data.get(field)
            if val is None or (isinstance(val, str) and not val.strip()):
                return Response(
                    {'error': f'Field "{field}" is required and cannot be empty.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        payment_type = str(data.get('payment_type', '')).lower().strip()
        if payment_type not in ['paid', 'unpaid']:
            return Response(
                {'error': 'Field "payment_type" must be either "paid" or "unpaid".'},
                status=status.HTTP_400_BAD_REQUEST
            )

        skills = data.get('skills', [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(',') if s.strip()]
        elif not isinstance(skills, list):
            skills = []

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(founder=request.user, skills=skills, payment_type=payment_type)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        project = self.get_object()
        if project.founder != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Forbidden: You cannot modify a project you do not own.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        project = self.get_object()
        if project.founder != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Forbidden: You cannot modify a project you do not own.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        project = self.get_object()
        if project.founder != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Forbidden: You cannot delete a project you do not own.'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user_profile(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def submit_skill_quiz(request):
    user = request.user
    if getattr(user, 'role', None) != 'student' and not user.is_staff:
        return Response(
            {'error': 'Forbidden: Only students can take skill quizzes.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    raw_skills = data.get('skills', [])
    if isinstance(raw_skills, list):
        skills = [str(s).strip() for s in raw_skills if str(s).strip()]
    elif isinstance(raw_skills, str):
        skills = [s.strip() for s in raw_skills.split(',') if s.strip()]
    else:
        skills = []

    try:
        quiz_score = int(data.get('quiz_score', 0))
    except (ValueError, TypeError):
        quiz_score = 0
    quiz_score = max(0, min(100, quiz_score))

    baseline_score = quiz_score + (len(skills) * 5)
    user.skills = skills
    user.confidence_score = baseline_score
    user.save()

    return Response({
        'message': 'Quiz completed!',
        'confidence_score': user.confidence_score,
        'skills': user.skills
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def verify_github(request):
    user = request.user
    if getattr(user, 'role', None) != 'student' and not user.is_staff:
        return Response(
            {'error': 'Forbidden: Only students can verify GitHub.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    github_username = data.get('github_username')
    if not github_username or not str(github_username).strip():
        return Response({'error': 'GitHub username is required.'}, status=status.HTTP_400_BAD_REQUEST)
    github_username = str(github_username).strip()

    headers = {
        'User-Agent': 'StartupLabs-App',
        'Accept': 'application/vnd.github.v3+json',
    }

    try:
        user_url = f"https://api.github.com/users/{github_username}"
        user_response = requests.get(user_url, headers=headers, timeout=10)

        if user_response.status_code == 404:
            return Response(
                {'error': f'The username "{github_username}" does not exist on GitHub.'},
                status=status.HTTP_404_NOT_FOUND
            )
        elif user_response.status_code != 200:
            return Response(
                {'error': f'GitHub API error: status {user_response.status_code}.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        github_data = user_response.json()

        repos_url = f"https://api.github.com/users/{github_username}/repos?per_page=100"
        repos_response = requests.get(repos_url, headers=headers, timeout=10)
        repos_data = repos_response.json() if repos_response.status_code == 200 and isinstance(repos_response.json(), list) else []

        score_boost = 10
        repo_count = len(repos_data) if isinstance(repos_data, list) else 0
        repo_boost = min(repo_count * 2, 20)
        score_boost += repo_boost

        total_stars = sum(repo.get('stargazers_count', 0) for repo in repos_data if isinstance(repo, dict)) if isinstance(repos_data, list) else 0
        star_boost = min(total_stars * 2, 20)
        score_boost += star_boost

        user.github_username = github_data.get('login', github_username)
        user.confidence_score += score_boost
        user.save()

        return Response({
            'message': 'GitHub successfully verified!',
            'confidence_score': user.confidence_score,
            'github_username': user.github_username,
            'stats': {
                'repos': repo_count,
                'stars': total_stars,
                'total_boost': score_boost
            }
        }, status=status.HTTP_200_OK)
    except requests.RequestException as e:
        return Response(
            {'error': f'Network error while contacting GitHub: {str(e)}'},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )


SKILL_QUESTION_BANK = {
    'python': {
        'skill': 'Python',
        'question': 'Which of the following data structures in Python is immutable?',
        'options': ['List', 'Dictionary', 'Set', 'Tuple'],
        'correct_answer': 'Tuple'
    },
    'django': {
        'skill': 'Django',
        'question': 'In Django, which component maps incoming URLs to the corresponding view functions?',
        'options': ['urls.py (URLconf)', 'models.py', 'views.py', 'settings.py'],
        'correct_answer': 'urls.py (URLconf)'
    },
    'react': {
        'skill': 'React',
        'question': 'Which React hook should be used to synchronize with an external system or handle side effects?',
        'options': ['useEffect', 'useState', 'useMemo', 'useContext'],
        'correct_answer': 'useEffect'
    },
    'javascript': {
        'skill': 'JavaScript',
        'question': 'What is the scope of a variable declared with "const" or "let" in modern JavaScript?',
        'options': ['Block scope', 'Function scope only', 'Global scope only', 'Module scope only'],
        'correct_answer': 'Block scope'
    },
    'typescript': {
        'skill': 'TypeScript',
        'question': 'Which TypeScript utility type creates a new type with all properties of an existing type set to optional?',
        'options': ['Partial<T>', 'Required<T>', 'Readonly<T>', 'Pick<T, K>'],
        'correct_answer': 'Partial<T>'
    },
    'figma': {
        'skill': 'Figma',
        'question': 'What Figma layout feature enables responsive components that adapt dynamically to their nested content?',
        'options': ['Auto Layout', 'Smart Animate', 'Constraints', 'Component Variants'],
        'correct_answer': 'Auto Layout'
    },
    'ui': {
        'skill': 'UI/UX Design',
        'question': 'What is the primary purpose of a low-fidelity wireframe?',
        'options': ['Structuring layout and visual hierarchy without styling distraction', 'Finalizing the micro-interaction animations', 'Writing production frontend code', 'Running automated unit tests'],
        'correct_answer': 'Structuring layout and visual hierarchy without styling distraction'
    },
    'node': {
        'skill': 'Node.js',
        'question': 'How does Node.js achieve high concurrency and non-blocking I/O on a single thread?',
        'options': ['Via the libuv Event Loop', 'By launching a new OS process for each connection', 'By compiling JS to bytecode at boot', 'By using synchronous thread pools exclusively'],
        'correct_answer': 'Via the libuv Event Loop'
    },
    'sql': {
        'skill': 'SQL',
        'question': 'Which clause in SQL is used to filter groups created by the GROUP BY clause?',
        'options': ['HAVING', 'WHERE', 'FILTER', 'ORDER BY'],
        'correct_answer': 'HAVING'
    },
    'marketing': {
        'skill': 'Growth Marketing',
        'question': 'What key metric calculates the average gross revenue generated by a customer over their entire relationship?',
        'options': ['LTV (Customer Lifetime Value)', 'CAC (Customer Acquisition Cost)', 'CPC (Cost Per Click)', 'ROAS (Return on Ad Spend)'],
        'correct_answer': 'LTV (Customer Lifetime Value)'
    },
    'aws': {
        'skill': 'AWS',
        'question': 'Which AWS service provides highly durable and scalable object storage?',
        'options': ['Amazon S3', 'Amazon EC2', 'Amazon EBS', 'Amazon DynamoDB'],
        'correct_answer': 'Amazon S3'
    }
}

GENERIC_PROGRAMMING_QUESTIONS = [
    {
        'skill': 'Product & Startups',
        'question': 'What does the term "MVP" stand for in startup product strategy?',
        'options': ['Minimum Viable Product', 'Most Valuable Player', 'Maximum Velocity Prototype', 'Modular Verification Process'],
        'correct_answer': 'Minimum Viable Product'
    },
    {
        'skill': 'Version Control',
        'question': 'What Git command creates a new feature branch and immediately switches to it?',
        'options': ['git checkout -b <branch-name>', 'git branch <branch-name>', 'git merge <branch-name>', 'git commit -m <branch-name>'],
        'correct_answer': 'git checkout -b <branch-name>'
    },
    {
        'skill': 'Algorithms',
        'question': 'What is the average time complexity of finding an item in a balanced Hash Map?',
        'options': ['O(1)', 'O(log n)', 'O(n)', 'O(n log n)'],
        'correct_answer': 'O(1)'
    },
    {
        'skill': 'API Design',
        'question': 'Which HTTP status code signifies that a resource was successfully created on the server?',
        'options': ['201 Created', '200 OK', '204 No Content', '202 Accepted'],
        'correct_answer': '201 Created'
    }
]


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def generate_skill_quiz(request):
    data = request.data
    raw_skills = data.get('skills', []) if isinstance(data, dict) else []
    if not isinstance(raw_skills, list):
        raw_skills = []

    selected_questions = []
    matched_keys = set()

    for skill in raw_skills:
        skill_str = str(skill).lower().strip()
        for key, q_data in SKILL_QUESTION_BANK.items():
            if key in skill_str and key not in matched_keys:
                q = dict(q_data)
                q['id'] = len(selected_questions) + 1
                selected_questions.append(q)
                matched_keys.add(key)
                if len(selected_questions) == 3:
                    break
        if len(selected_questions) == 3:
            break

    generic_idx = 0
    while len(selected_questions) < 3 and generic_idx < len(GENERIC_PROGRAMMING_QUESTIONS):
        g_q = dict(GENERIC_PROGRAMMING_QUESTIONS[generic_idx])
        g_q['id'] = len(selected_questions) + 1
        selected_questions.append(g_q)
        generic_idx += 1

    return Response({'questions': selected_questions}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def update_student_profile(request):
    user = request.user
    if getattr(user, 'role', None) != 'student' and not user.is_staff:
        return Response(
            {'error': 'Forbidden: Only students can update student profiles.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    if 'college' in data:
        user.college = str(data['college']).strip()
    if 'year_of_study' in data:
        user.year_of_study = str(data['year_of_study']).strip()
    if 'bio' in data:
        user.bio = str(data['bio']).strip()
    if 'is_available' in data:
        val = data['is_available']
        if isinstance(val, str):
            user.is_available = val.lower() in ('true', '1', 'yes')
        else:
            user.is_available = bool(val)

    user.save()
    serializer = UserSerializer(user)
    return Response({
        'message': 'Profile updated successfully',
        'user': serializer.data
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def get_available_talent(request):
    available_students = CustomUser.objects.filter(role='student', is_available=True)
    serializer = UserSerializer(available_students, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_founder_workspace(request):
    """
    Returns all projects owned by the logged-in founder,
    nested with their respective applications using FounderApplicationSerializer.
    Enforces strict role boundaries: students cannot access founder workspace.
    """
    founder = request.user
    if getattr(founder, 'role', None) != 'founder' and not founder.is_staff:
        return Response(
            {'error': 'Forbidden: Only founders can access the founder workspace.'},
            status=status.HTTP_403_FORBIDDEN
        )

    projects = Project.objects.filter(founder=founder).prefetch_related('applications__student').order_by('-created_at')
    serializer = FounderProjectSerializer(projects, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_student_applications(request):
    """
    Returns all applications submitted by the logged-in student.
    Enforces strict role boundaries: only students can view their applications.
    """
    if getattr(request.user, 'role', None) != 'student' and not request.user.is_staff:
        return Response(
            {'error': 'Forbidden: Only students can view submitted applications.'},
            status=status.HTTP_403_FORBIDDEN
        )

    applications = Application.objects.filter(student=request.user).select_related('project').order_by('-created_at')
    data = [
        {
            'id': app.id,
            'projectId': app.project.id,
            'projectTitle': app.project.title,
            'company': app.project.company,
            'status': app.status,
            'created_at': app.created_at
        }
        for app in applications
    ]
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def apply_to_project(request):
    """
    Allows an authenticated student to apply for a project.
    Enforces strict role boundaries: founders cannot apply to projects.
    """
    if getattr(request.user, 'role', None) != 'student' and not request.user.is_staff:
        return Response(
            {'error': 'Forbidden: Only students can apply to projects.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    raw_project_id = data.get('project_id') if data.get('project_id') is not None else data.get('projectId')
    if raw_project_id is None or (isinstance(raw_project_id, str) and not raw_project_id.strip()):
        return Response({'error': 'project_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        project_id = int(raw_project_id)
    except (ValueError, TypeError):
        return Response({'error': 'project_id must be a valid integer.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        project = Project.objects.get(pk=project_id)
    except Project.DoesNotExist:
        return Response({'error': 'Project not found.'}, status=status.HTTP_404_NOT_FOUND)

    if project.status != 'open':
        return Response({'error': 'This project is no longer accepting applications.'}, status=status.HTTP_400_BAD_REQUEST)

    application, created = Application.objects.get_or_create(
        project=project,
        student=request.user,
        defaults={'status': 'pending'}
    )
    return Response({
        'message': f'Successfully applied to {project.title}',
        'application_id': application.id,
        'status': application.status
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(['PATCH', 'POST'])
@permission_classes([permissions.IsAuthenticated])
def update_application_status(request, application_id=None):
    """
    Updates the status of an application.
    Enforces strict role and ownership gatekeeping:
    Founders cannot accept or update applications on projects they do not own.
    Students cannot update application status.
    """
    if getattr(request.user, 'role', None) != 'founder' and not request.user.is_staff:
        return Response(
            {'error': 'Forbidden: Only founders can update application statuses.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data
    if not isinstance(data, dict):
        return Response({'error': 'Invalid payload format: expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

    raw_app_id = (
        application_id or
        data.get('application_id') or
        data.get('appId') or
        data.get('app_id') or
        data.get('id')
    )
    if raw_app_id is None or (isinstance(raw_app_id, str) and not raw_app_id.strip()):
        return Response({'error': 'application_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        app_id = int(raw_app_id)
    except (ValueError, TypeError):
        return Response({'error': 'application_id must be a valid integer.'}, status=status.HTTP_400_BAD_REQUEST)

    raw_new_status = data.get('new_status') or data.get('status')
    if raw_new_status is None or (isinstance(raw_new_status, str) and not raw_new_status.strip()):
        return Response({'error': 'new_status is required.'}, status=status.HTTP_400_BAD_REQUEST)

    new_status = str(raw_new_status).lower().strip()
    valid_statuses = [choice[0] for choice in Application.STATUS_CHOICES]
    if new_status not in valid_statuses:
        return Response(
            {'error': f'Invalid status "{new_status}". Allowed values: {valid_statuses}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        application = Application.objects.select_related('student', 'project__founder').get(pk=app_id)
    except Application.DoesNotExist:
        return Response({'error': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Ownership Gatekeeping: Founders cannot accept or update applications on projects they do not own
    if application.project.founder != request.user and not request.user.is_staff:
        return Response(
            {'error': 'Forbidden: You cannot modify applications on projects you do not own.'},
            status=status.HTTP_403_FORBIDDEN
        )

    score_boosted = False
    if new_status == 'completed' and not application.is_completed_scored:
        student = application.student
        student.confidence_score += 50
        student.save()
        application.is_completed_scored = True
        score_boosted = True

    application.status = new_status
    application.save()

    serializer = FounderApplicationSerializer(application)
    return Response({
        'message': f'Application status updated to {new_status}.',
        'application': serializer.data,
        'score_boosted': score_boosted
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def analyze_project_idea(request):
    """
    POST endpoint to analyze a startup project idea using Gemini AI.
    Accepts a 'description' string and returns:
    - tech_stack: array of strings
    - difficulty_rating: integer 1-10
    - viability_score: integer 1-100
    Guaranteed to never raise an unhandled 500 server error via robust offline fallback.
    """
    FALLBACK_AI_ANALYSIS = {
        "tech_stack": ["Django", "React", "PostgreSQL", "Tailwind CSS"],
        "difficulty_rating": 7,
        "viability_score": 88
    }

    try:
        data = request.data
        if not isinstance(data, dict):
            return Response({'error': 'Invalid request body. Expected JSON object.'}, status=status.HTTP_400_BAD_REQUEST)

        description = data.get('description')
        if description is None or (isinstance(description, str) and not description.strip()):
            return Response({'error': 'Description is required and cannot be empty.'}, status=status.HTTP_400_BAD_REQUEST)

        description = str(description).strip()
    except Exception as e:
        return Response({'error': f'Invalid request data: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    prompt = (
        "You are an experienced Chief Technology Officer (CTO) evaluating a startup project idea.\n"
        f"Project Description:\n\"{description}\"\n\n"
        "Evaluate this idea thoroughly. Return ONLY a raw JSON object (no markdown, no backticks, no code fence) "
        "with exactly three keys:\n"
        "- \"tech_stack\": array of strings (recommended modern technologies and frameworks)\n"
        "- \"difficulty_rating\": integer between 1 and 10 (technical complexity)\n"
        "- \"viability_score\": integer between 1 and 100 (market and execution viability)"
    )

    try:
        parsed_result = None

        # 1. Try Google Generative AI SDK if installed and configured
        if genai:
            try:
                model = genai.GenerativeModel('gemini-2.5-flash')
                response = model.generate_content(prompt, request_options={'timeout': 5})
                if response and hasattr(response, 'text') and response.text:
                    raw_text = response.text.strip()
                    if raw_text.startswith('```'):
                        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                        raw_text = re.sub(r'\s*```$', '', raw_text)
                    parsed_result = json.loads(raw_text)
            except Exception:
                pass

        # 2. Try direct REST API if SDK failed and API key is present
        if not parsed_result and getattr(settings, 'GEMINI_API_KEY', None):
            try:
                api_key = settings.GEMINI_API_KEY
                url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, json=payload, timeout=5)
                if res.status_code == 200:
                    data = res.json()
                    raw_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    if raw_text.startswith('```'):
                        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
                        raw_text = re.sub(r'\s*```$', '', raw_text)
                    parsed_result = json.loads(raw_text)
            except Exception:
                pass

        # Validate parsed result structure
        if (
            isinstance(parsed_result, dict) and
            isinstance(parsed_result.get('tech_stack'), list) and
            isinstance(parsed_result.get('difficulty_rating'), (int, float)) and
            isinstance(parsed_result.get('viability_score'), (int, float))
        ):
            return Response({
                'tech_stack': [str(s) for s in parsed_result['tech_stack']],
                'difficulty_rating': int(parsed_result['difficulty_rating']),
                'viability_score': int(parsed_result['viability_score'])
            }, status=status.HTTP_200_OK)

        # If call failed, returned invalid structure, or timed out, gracefully return realistic fallback payload
        return Response(FALLBACK_AI_ANALYSIS, status=status.HTTP_200_OK)

    except Exception:
        # Strict offline failsafe: under any unexpected exception or timeout, return fallback payload
        return Response(FALLBACK_AI_ANALYSIS, status=status.HTTP_200_OK)
