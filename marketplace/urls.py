from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    register_user,
    get_user_profile,
    ProjectViewSet,
    submit_skill_quiz,
    verify_github,
    generate_skill_quiz,
    update_student_profile,
    get_available_talent,
    get_founder_workspace,
    update_application_status,
    apply_to_project,
    get_student_applications,
    analyze_project_idea,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')

urlpatterns = [
    # Router endpoints (e.g. /api/projects/)
    path('', include(router.urls)),

    # Authentication & User Profile
    path('auth/register/', register_user, name='register'),
    path('auth/me/', get_user_profile, name='user_profile'),

    # Student Endpoints
    path('student/quiz/', submit_skill_quiz, name='submit_skill_quiz'),
    path('student/quiz/generate/', generate_skill_quiz, name='generate_skill_quiz_alias'),
    path('student/github/', verify_github, name='verify_github'),
    path('student/generate_quiz/', generate_skill_quiz, name='generate_skill_quiz'),
    path('student/profile/update/', update_student_profile, name='update_student_profile'),
    path('student/applications/', get_student_applications, name='get_student_applications'),

    # Direct / Legacy Aliases for Student endpoints
    path('submit_skill_quiz/', submit_skill_quiz, name='submit_skill_quiz_direct'),
    path('verify_github/', verify_github, name='verify_github_direct'),
    path('generate_skill_quiz/', generate_skill_quiz, name='generate_skill_quiz_direct'),
    path('update_student_profile/', update_student_profile, name='update_student_profile_direct'),

    # Talent Discovery
    path('talent/available/', get_available_talent, name='get_available_talent'),
    path('get_available_talent/', get_available_talent, name='get_available_talent_direct'),

    # Founder Workspace
    path('founder/workspace/', get_founder_workspace, name='founder_workspace'),
    path('get_founder_workspace/', get_founder_workspace, name='get_founder_workspace_direct'),

    # Applications
    path('applications/apply/', apply_to_project, name='apply_to_project'),
    path('applications/my/', get_student_applications, name='get_student_applications_alias'),
    path('applications/status/', update_application_status, name='update_application_status'),
    path('applications/<int:application_id>/status/', update_application_status, name='update_application_status_param'),
    path('update_application_status/', update_application_status, name='update_application_status_direct'),
    path('founder/application/update/', update_application_status, name='update_application_status_founder'),

    # AI Project Analysis
    path('project/analyze/', analyze_project_idea, name='analyze_project_idea'),
    path('analyze_project_idea/', analyze_project_idea, name='analyze_project_idea_direct'),
    path('projects/analyze/', analyze_project_idea, name='analyze_project_idea_plural'),
    path('founder/project/analyze/', analyze_project_idea, name='analyze_project_idea_founder'),
]

