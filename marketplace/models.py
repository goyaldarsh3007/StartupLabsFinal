from django.db import models
from django.contrib.auth.models import AbstractUser

class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Student'),
        ('founder', 'Founder'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    full_name = models.CharField(max_length=255, blank=True)
    skills = models.JSONField(default=list, blank=True) # Stores ["Python", "Django", "React"]
    confidence_score = models.IntegerField(default=0)   # Dynamic score (0-100+)
    github_username = models.CharField(max_length=100, blank=True, null=True)
    college = models.CharField(max_length=255, blank=True)
    year_of_study = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True)
    is_available = models.BooleanField(default=False)

    @property
    def is_student(self):
        return self.role == 'student'

    @property
    def is_founder(self):
        return self.role == 'founder'

class Project(models.Model):
    founder = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='projects', null=True, blank=True)
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    description = models.TextField()
    duration = models.CharField(max_length=100)
    payment_type = models.CharField(max_length=50, choices=[('paid', 'Paid'), ('unpaid', 'Unpaid')])
    reward = models.CharField(max_length=100)
    skills = models.JSONField(default=list)
    status = models.CharField(max_length=20, default='open')
    ai_viability_score = models.IntegerField(default=0)
    ai_difficulty_rating = models.IntegerField(default=0)
    ai_tech_stack = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def owner(self):
        return self.founder

    @owner.setter
    def owner(self, value):
        self.founder = value

    def is_owned_by(self, user):
        return self.founder == user

    def __str__(self):
        return self.title

class Application(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('reviewing', 'Reviewing'),
        ('interviewing', 'Interviewing'),
        ('hired', 'Hired'),
        ('completed', 'Completed'),
        ('rejected', 'Rejected'),
    )
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='applications')
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    is_completed_scored = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.username} - {self.project.title} ({self.status})"

class Bookmark(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    class Meta:
        unique_together = ('project', 'user')
