# OpenAI Advisor Integration

AcademicPath uses the local ML/recommendation engine as the source of truth. The OpenAI-powered advisor is only an explanation layer.

## What OpenAI is allowed to do

- Explain the student's saved GPA, completed credits, failed/weak courses, and strengths/weaknesses.
- Explain the current ML recommendation output.
- Explain target-GPA feasibility flags.
- Answer course-specific questions only when the course exists in the loaded catalogue/context.

## What OpenAI is not allowed to do

- Invent course names, prerequisites, grades, policies, or AUB requirements.
- Replace the five local ML models.
- Claim validation on real AUB student records.

## Local setup

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-4o-mini
ADVISOR_USE_OPENAI=true
```

The `.env` file is intentionally ignored by Git. Keep it private.

If the key is missing, invalid, has no credits, or the internet is unavailable, the chatbot automatically falls back to the local grounded advisor.

## Architecture

1. Student asks a question.
2. Flask loads the logged-in student's saved profile, GPA, completed courses, target GPA, failed/weak courses, and recommendation output.
3. AcademicPath constructs a compact grounded context.
4. OpenAI rewrites/explains that context naturally.
5. If OpenAI fails, the deterministic local advisor returns a grounded answer.

This keeps the project aligned with Option A: the ML system remains the core contribution, and OpenAI improves the usability of the explanation interface.
