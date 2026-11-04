from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import CustomUser, Project, Application
from .serializers import UserSerializer, FounderApplicationSerializer, FounderProjectSerializer

class MarketplaceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='student@test.com',
            email='student@test.com',
            password='testpassword123',
            role='student',
            full_name='Test Student'
        )
        self.project = Project.objects.create(
            title='Test Project',
            company='Test Co',
            description='Test Description',
            duration='1 month',
            payment_type='paid',
            reward='$100',
            skills=['Python'],
            status='open'
        )

    def test_user_serializer_fields(self):
        """UserSerializer exposes skills, confidence_score, and github_username."""
        serializer = UserSerializer(self.user)
        self.assertIn('skills', serializer.data)
        self.assertIn('confidence_score', serializer.data)
        self.assertIn('github_username', serializer.data)
        self.assertEqual(serializer.data['confidence_score'], 0)
        self.assertEqual(serializer.data['skills'], [])

    def test_project_viewset_requires_authentication(self):
        """Unauthenticated users cannot view projects (401 Unauthorized)."""
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Authenticated user can view projects
        self.client.force_authenticate(user=self.user)
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_submit_skill_quiz(self):
        """submit_skill_quiz calculates baseline confidence score and updates user."""
        self.client.force_authenticate(user=self.user)
        payload = {
            'skills': ['Python', 'Django', 'React'],
            'quiz_score': 60
        }
        # Expected baseline: 60 + (3 * 5) = 75
        response = self.client.post('/api/student/quiz/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['confidence_score'], 75)
        self.assertEqual(response.data['skills'], ['Python', 'Django', 'React'])

        self.user.refresh_from_db()
        self.assertEqual(self.user.confidence_score, 75)
        self.assertEqual(self.user.skills, ['Python', 'Django', 'React'])

    @patch('requests.get')
    def test_verify_github_success(self, mock_get):
        """verify_github calls GitHub API, calculates boost (+10 base, repo boost, star boost) and saves to user."""
        self.client.force_authenticate(user=self.user)

        # Mock user response
        user_mock = MagicMock()
        user_mock.status_code = 200
        user_mock.json.return_value = {'login': 'octocat'}

        # Mock repos response: 3 repos, total 5 stars
        repos_mock = MagicMock()
        repos_mock.status_code = 200
        repos_mock.json.return_value = [
            {'name': 'repo1', 'stargazers_count': 2},
            {'name': 'repo2', 'stargazers_count': 3},
            {'name': 'repo3', 'stargazers_count': 0},
        ]

        # Side effect to return user_mock then repos_mock
        mock_get.side_effect = [user_mock, repos_mock]

        response = self.client.post('/api/student/github/', {'github_username': 'octocat'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Boost calculation:
        # Base: 10
        # Repos: min(3 * 2, 20) = 6
        # Stars: min(5 * 2, 20) = 10
        # Total boost = 10 + 6 + 10 = 26
        self.assertEqual(response.data['stats']['total_boost'], 26)
        self.assertEqual(response.data['stats']['repos'], 3)
        self.assertEqual(response.data['stats']['stars'], 5)
        self.assertEqual(response.data['github_username'], 'octocat')
        self.assertEqual(response.data['confidence_score'], 26)

        self.user.refresh_from_db()
        self.assertEqual(self.user.github_username, 'octocat')
        self.assertEqual(self.user.confidence_score, 26)

    @patch('requests.get')
    def test_verify_github_not_found(self, mock_get):
        """verify_github gracefully handles 404 when username does not exist."""
        self.client.force_authenticate(user=self.user)

        user_mock = MagicMock()
        user_mock.status_code = 404
        mock_get.return_value = user_mock

        response = self.client.post('/api/student/github/', {'github_username': 'non_existent_user_9999'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('does not exist', response.data['error'])

    def test_direct_url_aliases(self):
        """Direct URL aliases /api/submit_skill_quiz/ and /api/verify_github/ resolve properly."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post('/api/submit_skill_quiz/', {'skills': ['Go'], 'quiz_score': 50}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['confidence_score'], 55)

    def test_user_serializer_new_fields(self):
        """UserSerializer exposes college, year_of_study, bio, and is_available."""
        self.user.college = 'Stanford University'
        self.user.year_of_study = '3rd Year'
        self.user.bio = 'Passionate full-stack developer.'
        self.user.is_available = True
        self.user.save()

        serializer = UserSerializer(self.user)
        self.assertEqual(serializer.data['college'], 'Stanford University')
        self.assertEqual(serializer.data['year_of_study'], '3rd Year')
        self.assertEqual(serializer.data['bio'], 'Passionate full-stack developer.')
        self.assertTrue(serializer.data['is_available'])

    def test_generate_skill_quiz_tailored(self):
        """generate_skill_quiz returns 3 dynamic questions tailored to submitted skills."""
        response = self.client.post('/api/student/generate_quiz/', {'skills': ['Python', 'React']}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        questions = response.data.get('questions', [])
        self.assertEqual(len(questions), 3)

        skills_returned = [q['skill'] for q in questions]
        self.assertIn('Python', skills_returned)
        self.assertIn('React', skills_returned)

    def test_generate_skill_quiz_generic_fallback(self):
        """generate_skill_quiz falls back to generic questions if empty or unknown skills provided."""
        response = self.client.post('/api/generate_skill_quiz/', {'skills': []}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        questions = response.data.get('questions', [])
        self.assertEqual(len(questions), 3)

    def test_update_student_profile(self):
        """update_student_profile saves college, year_of_study, bio, and is_available toggle."""
        self.client.force_authenticate(user=self.user)
        payload = {
            'college': 'MIT',
            'year_of_study': 'Senior',
            'bio': 'AI & Web Engineer',
            'is_available': True
        }
        response = self.client.post('/api/student/profile/update/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['college'], 'MIT')
        self.assertEqual(response.data['user']['year_of_study'], 'Senior')
        self.assertEqual(response.data['user']['bio'], 'AI & Web Engineer')
        self.assertTrue(response.data['user']['is_available'])

        self.user.refresh_from_db()
        self.assertEqual(self.user.college, 'MIT')
        self.assertEqual(self.user.year_of_study, 'Senior')
        self.assertEqual(self.user.bio, 'AI & Web Engineer')
        self.assertTrue(self.user.is_available)

    def test_get_available_talent_filters_correctly(self):
        """get_available_talent returns ONLY users where role='student' and is_available=True."""
        # Current user is student, set available
        self.user.is_available = True
        self.user.save()

        # Another student who is NOT available
        CustomUser.objects.create_user(
            username='unavailable_student@test.com',
            email='unavailable_student@test.com',
            password='password123',
            role='student',
            is_available=False
        )

        # A founder who IS available (should not be in talent pool)
        CustomUser.objects.create_user(
            username='founder@test.com',
            email='founder@test.com',
            password='password123',
            role='founder',
            is_available=True
        )

        response = self.client.get('/api/talent/available/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [u['username'] for u in response.data]
        self.assertIn(self.user.username, usernames)
        self.assertEqual(len(usernames), 1)

    def test_founder_application_serializer(self):
        """FounderApplicationSerializer exposes student name, skills, and confidence score."""
        self.user.skills = ['Python', 'Django']
        self.user.confidence_score = 45
        self.user.full_name = 'Alice Smith'
        self.user.save()

        app = Application.objects.create(
            project=self.project,
            student=self.user,
            status='pending'
        )
        serializer = FounderApplicationSerializer(app)
        self.assertEqual(serializer.data['student_name'], 'Alice Smith')
        self.assertEqual(serializer.data['name'], 'Alice Smith')
        self.assertEqual(serializer.data['skills'], ['Python', 'Django'])
        self.assertEqual(serializer.data['confidence_score'], 45)
        self.assertFalse(serializer.data['is_completed_scored'])

    def test_get_founder_workspace(self):
        """get_founder_workspace returns only projects owned by the logged-in founder with nested applications."""
        founder1 = CustomUser.objects.create_user(
            username='founder1@test.com',
            email='founder1@test.com',
            password='password123',
            role='founder'
        )
        founder2 = CustomUser.objects.create_user(
            username='founder2@test.com',
            email='founder2@test.com',
            password='password123',
            role='founder'
        )
        proj1 = Project.objects.create(
            founder=founder1,
            title='Founder1 Project',
            company='Startup1',
            duration='2 weeks',
            payment_type='paid',
            reward='$500'
        )
        Project.objects.create(
            founder=founder2,
            title='Founder2 Project',
            company='Startup2',
            duration='1 month',
            payment_type='unpaid',
            reward='Equity'
        )
        Application.objects.create(
            project=proj1,
            student=self.user,
            status='pending'
        )

        self.client.force_authenticate(user=founder1)
        response = self.client.get('/api/founder/workspace/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Founder1 Project')
        self.assertEqual(len(response.data[0]['applications']), 1)
        self.assertEqual(response.data[0]['applications'][0]['student_name'], 'Test Student')

    def test_update_application_status_to_interviewing(self):
        """Updating status to non-completed does not alter confidence score."""
        app = Application.objects.create(
            project=self.project,
            student=self.user,
            status='pending'
        )
        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            f'/api/applications/{app.id}/status/',
            {'new_status': 'interviewing'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['application']['status'], 'interviewing')
        self.assertFalse(response.data['score_boosted'])

        app.refresh_from_db()
        self.assertEqual(app.status, 'interviewing')
        self.assertFalse(app.is_completed_scored)
        self.user.refresh_from_db()
        self.assertEqual(self.user.confidence_score, 0)

    def test_update_application_status_to_completed_boosts_score(self):
        """Updating status to 'completed' adds 50 points to confidence_score and marks is_completed_scored."""
        app = Application.objects.create(
            project=self.project,
            student=self.user,
            status='hired',
            is_completed_scored=False
        )
        self.user.confidence_score = 30
        self.user.save()

        self.client.force_authenticate(user=self.user)
        response = self.client.patch(
            '/api/applications/status/',
            {'application_id': app.id, 'new_status': 'completed'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['score_boosted'])
        self.assertEqual(response.data['application']['status'], 'completed')
        self.assertTrue(response.data['application']['is_completed_scored'])

        self.user.refresh_from_db()
        self.assertEqual(self.user.confidence_score, 80)  # 30 + 50 = 80

        app.refresh_from_db()
        self.assertTrue(app.is_completed_scored)
        self.assertEqual(app.status, 'completed')

        # Test idempotency: Calling it again does not add another 50 points
        response2 = self.client.patch(
            '/api/applications/status/',
            {'application_id': app.id, 'new_status': 'completed'},
            format='json'
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['score_boosted'])
        self.user.refresh_from_db()
        self.assertEqual(self.user.confidence_score, 80)

    def test_project_ai_fields_and_serializer(self):
        """Project model and serializer include ai_viability_score, ai_difficulty_rating, and ai_tech_stack."""
        project = Project.objects.create(
            title='AI Health Assistant',
            company='HealthCorp',
            description='An AI agent for personal health tracking',
            duration='3 months',
            payment_type='paid',
            reward='$500',
            skills=['Python', 'PyTorch'],
            ai_viability_score=85,
            ai_difficulty_rating=7,
            ai_tech_stack=['Python', 'FastAPI', 'PyTorch']
        )
        self.assertEqual(project.ai_viability_score, 85)
        self.assertEqual(project.ai_difficulty_rating, 7)
        self.assertEqual(project.ai_tech_stack, ['Python', 'FastAPI', 'PyTorch'])

        from .serializers import ProjectSerializer
        serializer = ProjectSerializer(project)
        self.assertIn('ai_viability_score', serializer.data)
        self.assertIn('ai_difficulty_rating', serializer.data)
        self.assertIn('ai_tech_stack', serializer.data)
        self.assertEqual(serializer.data['ai_viability_score'], 85)

    def test_analyze_project_idea_validation(self):
        """analyze_project_idea returns 400 if description is missing."""
        response = self.client.post('/api/project/analyze/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_analyze_project_idea_success(self):
        """analyze_project_idea returns tech_stack, difficulty_rating, and viability_score."""
        payload = {'description': 'A smart tutoring platform with AI-generated quizzes and instant grading.'}
        response = self.client.post('/api/project/analyze/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('tech_stack', response.data)
        self.assertIn('difficulty_rating', response.data)
        self.assertIn('viability_score', response.data)
        self.assertIsInstance(response.data['tech_stack'], list)
        self.assertIsInstance(response.data['difficulty_rating'], int)
        self.assertIsInstance(response.data['viability_score'], int)

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_project_idea_with_mocked_gemini(self, mock_model_class):
        """analyze_project_idea initializes gemini-2.5-flash and parses returned JSON."""
        mock_instance = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"tech_stack": ["React", "FastAPI", "PostgreSQL"], "difficulty_rating": 6, "viability_score": 88}'
        mock_instance.generate_content.return_value = mock_response
        mock_model_class.return_value = mock_instance

        payload = {'description': 'A modern developer tooling platform.'}
        response = self.client.post('/api/project/analyze/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mock_model_class.assert_called_with('gemini-2.5-flash')
        self.assertEqual(response.data['tech_stack'], ["React", "FastAPI", "PostgreSQL"])
        self.assertEqual(response.data['difficulty_rating'], 6)
        self.assertEqual(response.data['viability_score'], 88)

