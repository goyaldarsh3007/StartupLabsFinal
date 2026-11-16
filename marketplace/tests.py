from unittest.mock import patch, MagicMock
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import CustomUser, Project, Application
from .serializers import UserSerializer, FounderApplicationSerializer, FounderProjectSerializer


class MarketplaceApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.student = CustomUser.objects.create_user(
            username='student@test.com',
            email='student@test.com',
            password='testpassword123',
            role='student',
            full_name='Test Student'
        )
        self.founder = CustomUser.objects.create_user(
            username='founder@test.com',
            email='founder@test.com',
            password='testpassword123',
            role='founder',
            full_name='Test Founder'
        )
        self.other_founder = CustomUser.objects.create_user(
            username='other_founder@test.com',
            email='other_founder@test.com',
            password='testpassword123',
            role='founder',
            full_name='Other Founder'
        )
        self.project = Project.objects.create(
            founder=self.founder,
            title='Test Project',
            company='Test Co',
            description='Test Description',
            duration='1 month',
            payment_type='paid',
            reward='$100',
            skills=['Python'],
            status='open'
        )
        # Backward compatibility alias for tests referencing self.user
        self.user = self.student

    def test_user_serializer_fields(self):
        """UserSerializer exposes skills, confidence_score, and github_username."""
        serializer = UserSerializer(self.student)
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
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/projects/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---------------- ROLE GATEKEEPING: PROJECT CREATION & MANAGEMENT ----------------
    def test_student_cannot_create_project(self):
        """Students cannot create projects (403 Forbidden)."""
        self.client.force_authenticate(user=self.student)
        payload = {
            'title': 'Student Attempt Project',
            'company': 'Unauthorized Corp',
            'description': 'Students should not create projects',
            'duration': '1 month',
            'payment_type': 'paid',
            'reward': '$500',
            'skills': ['Python']
        }
        response = self.client.post('/api/projects/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Forbidden', response.data['error'])

    def test_founder_can_create_project(self):
        """Founders can create projects with valid payload (201 Created)."""
        self.client.force_authenticate(user=self.founder)
        payload = {
            'title': 'Valid Founder Project',
            'company': 'Founder Labs',
            'description': 'Building next-generation fintech platform',
            'duration': '3 months',
            'payment_type': 'paid',
            'reward': '$1500',
            'skills': ['Python', 'Django', 'React']
        }
        response = self.client.post('/api/projects/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['title'], 'Valid Founder Project')
        self.assertEqual(response.data['founder'], self.founder.id)

    def test_project_creation_input_validation(self):
        """Project creation validates required fields and payment_type (400 Bad Request)."""
        self.client.force_authenticate(user=self.founder)

        # Missing required field
        response = self.client.post('/api/projects/', {'title': 'Only Title'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Empty string in required field
        invalid_payload = {
            'title': '   ',
            'company': 'Founder Labs',
            'description': 'Valid desc',
            'duration': '1 month',
            'payment_type': 'paid',
            'reward': '$500'
        }
        response = self.client.post('/api/projects/', invalid_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid payment_type
        invalid_payment_payload = {
            'title': 'Valid Title',
            'company': 'Founder Labs',
            'description': 'Valid desc',
            'duration': '1 month',
            'payment_type': 'invalid_type',
            'reward': '$500'
        }
        response = self.client.post('/api/projects/', invalid_payment_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_founder_cannot_modify_other_founder_project(self):
        """A founder cannot update or delete a project owned by another founder (403 Forbidden)."""
        self.client.force_authenticate(user=self.other_founder)

        response = self.client.patch(
            f'/api/projects/{self.project.id}/',
            {'title': 'Hijacked Title'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        delete_response = self.client.delete(f'/api/projects/{self.project.id}/')
        self.assertEqual(delete_response.status_code, status.HTTP_403_FORBIDDEN)

    # ---------------- ROLE GATEKEEPING: FOUNDER WORKSPACE ----------------
    def test_student_cannot_access_founder_workspace(self):
        """Students cannot access the founder workspace (403 Forbidden)."""
        self.client.force_authenticate(user=self.student)
        response = self.client.get('/api/founder/workspace/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Forbidden', response.data['error'])

    def test_get_founder_workspace_returns_owned_projects(self):
        """get_founder_workspace returns only projects owned by the logged-in founder with real applications."""
        proj2 = Project.objects.create(
            founder=self.other_founder,
            title='Other Project',
            company='Other Startup',
            duration='1 month',
            payment_type='unpaid',
            reward='Equity'
        )
        Application.objects.create(
            project=self.project,
            student=self.student,
            status='pending'
        )

        self.client.force_authenticate(user=self.founder)
        response = self.client.get('/api/founder/workspace/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['title'], 'Test Project')
        self.assertEqual(len(response.data[0]['applications']), 1)
        self.assertEqual(response.data[0]['applications'][0]['student_name'], 'Test Student')

    # ---------------- ROLE GATEKEEPING: PROJECT APPLICATIONS ----------------
    def test_founder_cannot_apply_to_project(self):
        """Founders cannot apply to projects (403 Forbidden)."""
        self.client.force_authenticate(user=self.founder)
        response = self.client.post('/api/applications/apply/', {'project_id': self.project.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Forbidden', response.data['error'])

    def test_student_can_apply_to_project(self):
        """Students can apply to open projects (201 Created)."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/applications/apply/', {'project_id': self.project.id}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['status'], 'pending')

        # Idempotent apply returns 200 OK
        response2 = self.client.post('/api/applications/apply/', {'project_id': self.project.id}, format='json')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

    def test_apply_to_project_input_validation(self):
        """apply_to_project validates missing or malformed project_id and closed projects."""
        self.client.force_authenticate(user=self.student)

        # Missing project_id
        res1 = self.client.post('/api/applications/apply/', {}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-integer project_id
        res2 = self.client.post('/api/applications/apply/', {'project_id': 'abc'}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Non-existent project
        res3 = self.client.post('/api/applications/apply/', {'project_id': 99999}, format='json')
        self.assertEqual(res3.status_code, status.HTTP_404_NOT_FOUND)

        # Closed project
        self.project.status = 'closed'
        self.project.save()
        res4 = self.client.post('/api/applications/apply/', {'project_id': self.project.id}, format='json')
        self.assertEqual(res4.status_code, status.HTTP_400_BAD_REQUEST)

    # ---------------- ROLE GATEKEEPING: APPLICATION STATUS UPDATES ----------------
    def test_student_cannot_update_application_status(self):
        """Students cannot update application status (403 Forbidden)."""
        app = Application.objects.create(
            project=self.project,
            student=self.student,
            status='pending'
        )
        self.client.force_authenticate(user=self.student)
        response = self.client.patch(
            f'/api/applications/{app.id}/status/',
            {'new_status': 'hired'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Forbidden', response.data['error'])

    def test_founder_cannot_update_application_on_unowned_project(self):
        """Founders cannot update applications on projects they do not own (403 Forbidden)."""
        app = Application.objects.create(
            project=self.project,  # Owned by self.founder
            student=self.student,
            status='pending'
        )
        # Attempt update as other_founder
        self.client.force_authenticate(user=self.other_founder)
        response = self.client.patch(
            f'/api/applications/{app.id}/status/',
            {'new_status': 'interviewing'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('Forbidden', response.data['error'])

    def test_owner_founder_can_update_application_status(self):
        """The owning founder can successfully update application status."""
        app = Application.objects.create(
            project=self.project,
            student=self.student,
            status='pending'
        )
        self.client.force_authenticate(user=self.founder)
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

    def test_update_application_status_input_validation(self):
        """update_application_status validates application_id, status choices, and missing fields."""
        self.client.force_authenticate(user=self.founder)

        # Missing application_id
        res1 = self.client.patch('/api/applications/status/', {'new_status': 'hired'}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing new_status
        app = Application.objects.create(project=self.project, student=self.student, status='pending')
        res2 = self.client.patch(f'/api/applications/{app.id}/status/', {}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Invalid status choice
        res3 = self.client.patch(f'/api/applications/{app.id}/status/', {'new_status': 'super_hired'}, format='json')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_application_status_to_completed_boosts_score(self):
        """Updating status to 'completed' adds 50 points to confidence_score and marks is_completed_scored."""
        app = Application.objects.create(
            project=self.project,
            student=self.student,
            status='hired',
            is_completed_scored=False
        )
        self.student.confidence_score = 30
        self.student.save()

        self.client.force_authenticate(user=self.founder)
        response = self.client.patch(
            '/api/applications/status/',
            {'application_id': app.id, 'new_status': 'completed'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['score_boosted'])
        self.assertEqual(response.data['application']['status'], 'completed')
        self.assertTrue(response.data['application']['is_completed_scored'])

        self.student.refresh_from_db()
        self.assertEqual(self.student.confidence_score, 80)

        app.refresh_from_db()
        self.assertTrue(app.is_completed_scored)
        self.assertEqual(app.status, 'completed')

        # Idempotency: Calling it again does not add another 50 points
        response2 = self.client.patch(
            '/api/applications/status/',
            {'application_id': app.id, 'new_status': 'completed'},
            format='json'
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertFalse(response2.data['score_boosted'])
        self.student.refresh_from_db()
        self.assertEqual(self.student.confidence_score, 80)

    def test_get_student_applications_endpoint(self):
        """Students can view their submitted applications, while founders are forbidden."""
        app = Application.objects.create(project=self.project, student=self.student, status='pending')

        # Student access
        self.client.force_authenticate(user=self.student)
        res = self.client.get('/api/student/applications/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]['projectTitle'], 'Test Project')

        # Founder access forbidden
        self.client.force_authenticate(user=self.founder)
        res_founder = self.client.get('/api/student/applications/')
        self.assertEqual(res_founder.status_code, status.HTTP_403_FORBIDDEN)

    # ---------------- ROBUST OFFLINE FAILSAFE (GEMINI API) ----------------
    def test_analyze_project_idea_validation(self):
        """analyze_project_idea returns 400 if description is missing or blank."""
        response = self.client.post('/api/project/analyze/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

        response_blank = self.client.post('/api/project/analyze/', {'description': '   '}, format='json')
        self.assertEqual(response_blank.status_code, status.HTTP_400_BAD_REQUEST)

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

    @patch('google.generativeai.GenerativeModel')
    def test_analyze_project_idea_gemini_exception_graceful_fallback(self, mock_model_class):
        """When Gemini throws any exception/timeout/network error, gracefully returns fallback payload without 500 error."""
        mock_instance = MagicMock()
        mock_instance.generate_content.side_effect = Exception("Gemini network timeout / quota exceeded")
        mock_model_class.return_value = mock_instance

        payload = {'description': 'Autonomous drone delivery service.'}
        response = self.client.post('/api/project/analyze/', payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Expected exact fallback payload per protocol specification:
        # {"tech_stack": ["Django", "React", "PostgreSQL", "Tailwind CSS"], "difficulty_rating": 7, "viability_score": 88}
        self.assertEqual(response.data['tech_stack'], ["Django", "React", "PostgreSQL", "Tailwind CSS"])
        self.assertEqual(response.data['difficulty_rating'], 7)
        self.assertEqual(response.data['viability_score'], 88)

    # ---------------- STUDENT SKILL QUIZ, GITHUB & PROFILE ----------------
    def test_submit_skill_quiz(self):
        """submit_skill_quiz calculates baseline confidence score and updates user."""
        self.client.force_authenticate(user=self.student)
        payload = {
            'skills': ['Python', 'Django', 'React'],
            'quiz_score': 60
        }
        response = self.client.post('/api/student/quiz/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['confidence_score'], 75)
        self.assertEqual(response.data['skills'], ['Python', 'Django', 'React'])

        self.student.refresh_from_db()
        self.assertEqual(self.student.confidence_score, 75)
        self.assertEqual(self.student.skills, ['Python', 'Django', 'React'])

    def test_founder_cannot_submit_skill_quiz(self):
        """Founders cannot take student skill quizzes (403 Forbidden)."""
        self.client.force_authenticate(user=self.founder)
        response = self.client.post('/api/student/quiz/', {'skills': ['Python'], 'quiz_score': 50}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @patch('requests.get')
    def test_verify_github_success(self, mock_get):
        """verify_github calls GitHub API, calculates boost (+10 base, repo boost, star boost) and saves to user."""
        self.client.force_authenticate(user=self.student)

        user_mock = MagicMock()
        user_mock.status_code = 200
        user_mock.json.return_value = {'login': 'octocat'}

        repos_mock = MagicMock()
        repos_mock.status_code = 200
        repos_mock.json.return_value = [
            {'name': 'repo1', 'stargazers_count': 2},
            {'name': 'repo2', 'stargazers_count': 3},
            {'name': 'repo3', 'stargazers_count': 0},
        ]

        mock_get.side_effect = [user_mock, repos_mock]

        response = self.client.post('/api/student/github/', {'github_username': 'octocat'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['stats']['total_boost'], 26)
        self.assertEqual(response.data['stats']['repos'], 3)
        self.assertEqual(response.data['stats']['stars'], 5)
        self.assertEqual(response.data['github_username'], 'octocat')
        self.assertEqual(response.data['confidence_score'], 26)

        self.student.refresh_from_db()
        self.assertEqual(self.student.github_username, 'octocat')
        self.assertEqual(self.student.confidence_score, 26)

    @patch('requests.get')
    def test_verify_github_not_found(self, mock_get):
        """verify_github gracefully handles 404 when username does not exist."""
        self.client.force_authenticate(user=self.student)

        user_mock = MagicMock()
        user_mock.status_code = 404
        mock_get.return_value = user_mock

        response = self.client.post('/api/student/github/', {'github_username': 'non_existent_user_9999'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('does not exist', response.data['error'])

    def test_direct_url_aliases(self):
        """Direct URL aliases resolve properly."""
        self.client.force_authenticate(user=self.student)
        response = self.client.post('/api/submit_skill_quiz/', {'skills': ['Go'], 'quiz_score': 50}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['confidence_score'], 55)

    def test_user_serializer_new_fields(self):
        """UserSerializer exposes college, year_of_study, bio, and is_available."""
        self.student.college = 'Stanford University'
        self.student.year_of_study = '3rd Year'
        self.student.bio = 'Passionate full-stack developer.'
        self.student.is_available = True
        self.student.save()

        serializer = UserSerializer(self.student)
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
        self.client.force_authenticate(user=self.student)
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

        self.student.refresh_from_db()
        self.assertEqual(self.student.college, 'MIT')
        self.assertEqual(self.student.year_of_study, 'Senior')
        self.assertEqual(self.student.bio, 'AI & Web Engineer')
        self.assertTrue(self.student.is_available)

    def test_get_available_talent_filters_correctly(self):
        """get_available_talent returns ONLY users where role='student' and is_available=True."""
        self.student.is_available = True
        self.student.save()

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
            username='available_founder@test.com',
            email='available_founder@test.com',
            password='password123',
            role='founder',
            is_available=True
        )

        response = self.client.get('/api/talent/available/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [u['username'] for u in response.data]
        self.assertIn(self.student.username, usernames)
        self.assertEqual(len(usernames), 1)

    def test_founder_application_serializer(self):
        """FounderApplicationSerializer exposes student name, skills, and confidence score."""
        self.student.skills = ['Python', 'Django']
        self.student.confidence_score = 45
        self.student.full_name = 'Alice Smith'
        self.student.save()

        app = Application.objects.create(
            project=self.project,
            student=self.student,
            status='pending'
        )
        serializer = FounderApplicationSerializer(app)
        self.assertEqual(serializer.data['student_name'], 'Alice Smith')
        self.assertEqual(serializer.data['name'], 'Alice Smith')
        self.assertEqual(serializer.data['skills'], ['Python', 'Django'])
        self.assertEqual(serializer.data['confidence_score'], 45)
        self.assertFalse(serializer.data['is_completed_scored'])
