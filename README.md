# StartupLabs

StartupLabs is a web platform connecting student developers with startup founders for collaborative projects, internships, and freelance opportunities. It integrates Google Gemini AI for smart project viability scoring, difficulty assessment, and tech-stack matching.

## Features

- **User Roles**: Tailored experiences for Students and Founders.
- **Project Marketplace**: Founders post projects with duration, compensation details, and required skills.
- **AI Scoring & Analysis**: Powered by Google Gemini AI to analyze project descriptions, calculate viability scores, suggest tech stacks, and evaluate applicant fit.
- **Application Workflow**: Transparent lifecycle tracking from submission, review, and interview to hire.

## Tech Stack

- **Backend**: Django, Django REST Framework, SimpleJWT
- **Database**: SQLite (Development)
- **AI Integration**: Google Generative AI (Gemini)
- **Frontend**: Django Templates, Static Assets

## Getting Started

### Prerequisites

- Python 3.10+
- A Google Gemini API Key

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/goyaldarsh3007/StartupLabs.git
   cd StartupLabs
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   Copy `.env.example` to `.env` and provide your Gemini API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env`:
   ```env
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Start the development server:**
   ```bash
   python manage.py runserver
   ```
   Open [http://localhost:8000](http://localhost:8000) in your browser.
