-- Content hashes on existing resume/JD rows + interview dossier cache table

ALTER TABLE resumes ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE job_descriptions ADD COLUMN IF NOT EXISTS content_hash TEXT;

CREATE INDEX IF NOT EXISTS idx_resumes_user_content_hash
    ON resumes(user_id, content_hash);
CREATE INDEX IF NOT EXISTS idx_jd_user_content_hash
    ON job_descriptions(user_id, content_hash);

CREATE TABLE IF NOT EXISTS interview_dossiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_id UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    jd_id UUID NOT NULL REFERENCES job_descriptions(id) ON DELETE CASCADE,
    job_title TEXT,
    source TEXT,
    dossier JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (resume_id, jd_id)
);

CREATE INDEX IF NOT EXISTS idx_interview_dossiers_user_pair
    ON interview_dossiers(user_id, resume_id, jd_id);
