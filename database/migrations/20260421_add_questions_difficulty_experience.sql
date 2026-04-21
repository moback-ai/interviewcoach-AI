ALTER TABLE questions
ADD COLUMN IF NOT EXISTS difficulty_experience TEXT NOT NULL DEFAULT 'beginner';
