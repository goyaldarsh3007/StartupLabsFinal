from rest_framework import serializers
from .models import CustomUser, Project, Application, Bookmark

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'role', 'full_name',
            'skills', 'confidence_score', 'github_username',
            'college', 'year_of_study', 'bio', 'is_available'
        ]
        read_only_fields = ['id', 'username']

class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = '__all__'
        read_only_fields = ['founder', 'created_at']

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ['student', 'created_at', 'is_completed_scored']

class FounderApplicationSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    student_email = serializers.CharField(source='student.email', read_only=True)
    skills = serializers.JSONField(source='student.skills', read_only=True)
    confidence_score = serializers.IntegerField(source='student.confidence_score', read_only=True)
    student_college = serializers.CharField(source='student.college', read_only=True)
    student_year_of_study = serializers.CharField(source='student.year_of_study', read_only=True)
    student_bio = serializers.CharField(source='student.bio', read_only=True)
    student_github_username = serializers.CharField(source='student.github_username', read_only=True)

    class Meta:
        model = Application
        fields = [
            'id', 'project', 'student', 'status', 'is_completed_scored', 'created_at',
            'student_name', 'name', 'student_email', 'skills', 'confidence_score',
            'student_college', 'student_year_of_study', 'student_bio', 'student_github_username'
        ]
        read_only_fields = ['student_name', 'name', 'student_email', 'skills', 'confidence_score']

    def get_student_name(self, obj):
        return obj.student.full_name or obj.student.username

    def get_name(self, obj):
        return obj.student.full_name or obj.student.username

class FounderProjectSerializer(serializers.ModelSerializer):
    applications = FounderApplicationSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = '__all__'
