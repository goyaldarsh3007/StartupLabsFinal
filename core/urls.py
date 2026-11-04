from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from marketplace.views import (
    index,
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
    analyze_project_idea,
)

router = DefaultRouter()
router.register(r'projects', ProjectViewSet)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', index, name='index'),
    path('api/auth/register/', register_user, name='register'),
    path('api/auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/auth/me/', get_user_profile, name='user_profile'),
    path('api/', include(router.urls)),
    path('api/student/quiz/', submit_skill_quiz, name='submit_skill_quiz'),
    path('api/student/quiz/generate/', generate_skill_quiz, name='generate_skill_quiz_alias'),
    path('api/student/github/', verify_github, name='verify_github'),
    path('api/submit_skill_quiz/', submit_skill_quiz, name='submit_skill_quiz_direct'),
    path('api/verify_github/', verify_github, name='verify_github_direct'),
    path('api/student/generate_quiz/', generate_skill_quiz, name='generate_skill_quiz'),
    path('api/generate_skill_quiz/', generate_skill_quiz, name='generate_skill_quiz_direct'),
    path('api/student/profile/update/', update_student_profile, name='update_student_profile'),
    path('api/update_student_profile/', update_student_profile, name='update_student_profile_direct'),
    path('api/talent/available/', get_available_talent, name='get_available_talent'),
    path('api/get_available_talent/', get_available_talent, name='get_available_talent_direct'),
    path('api/founder/workspace/', get_founder_workspace, name='founder_workspace'),
    path('api/get_founder_workspace/', get_founder_workspace, name='get_founder_workspace_direct'),
    path('api/applications/status/', update_application_status, name='update_application_status'),
    path('api/applications/<int:application_id>/status/', update_application_status, name='update_application_status_param'),
    path('api/update_application_status/', update_application_status, name='update_application_status_direct'),
    path('api/founder/application/update/', update_application_status, name='update_application_status_founder'),
    path('api/applications/apply/', apply_to_project, name='apply_to_project'),
    path('api/project/analyze/', analyze_project_idea, name='analyze_project_idea'),
    path('api/analyze_project_idea/', analyze_project_idea, name='analyze_project_idea_direct'),
    path('api/projects/analyze/', analyze_project_idea, name='analyze_project_idea_plural'),
    path('api/founder/project/analyze/', analyze_project_idea, name='analyze_project_idea_founder'),
]


