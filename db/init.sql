CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE emails (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp_received TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sender_email VARCHAR(255) NOT NULL DEFAULT 'UNKNOWN_SENDER',
    sender_name VARCHAR(255),
    recipients TEXT[] NOT NULL DEFAULT '{}',
    subject VARCHAR(1000),
    body_plain TEXT,
    body_html TEXT,
    headers_raw JSONB NOT NULL DEFAULT '{}',
    raw_email_blob BYTEA,
    size_bytes BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE threat_analysis (
    analysis_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES emails(message_id) ON DELETE CASCADE,
    spf_score INT CHECK (spf_score >= 0 AND spf_score <= 10),
    dkim_score INT CHECK (dkim_score >= 0 AND dkim_score <= 10),
    auth_combined_score INT,
    urls_found INT DEFAULT 0,
    url_analysis JSONB DEFAULT '{}',
    highest_url_risk VARCHAR(20) DEFAULT 'UNKNOWN_RISK',
    attachments_found INT DEFAULT 0,
    attachment_analysis JSONB DEFAULT '{}',
    highest_attachment_risk VARCHAR(20) DEFAULT 'LOW_RISK',
    gemini_classification JSONB DEFAULT '{}',
    sender_reputation INT CHECK (sender_reputation >= 0 AND sender_reputation <= 100),
    sender_domain VARCHAR(255),
    domain_age_days INT,
    composite_threat_score INT CHECK (composite_threat_score >= 0 AND composite_threat_score <= 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE decisions (
    decision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES emails(message_id) ON DELETE CASCADE,
    analysis_id UUID REFERENCES threat_analysis(analysis_id),
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('ALLOW', 'QUARANTINE', 'BLOCK')),
    threat_score INT,
    reasoning JSONB DEFAULT '{}',
    user_feedback VARCHAR(20) CHECK (user_feedback IN ('SAFE', 'SPAM') OR user_feedback IS NULL),
    user_id UUID,
    feedback_timestamp TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE sender_reputation (
    sender_domain VARCHAR(255) PRIMARY KEY,
    reputation_score INT DEFAULT 50 CHECK (reputation_score >= 0 AND reputation_score <= 100),
    successful_emails INT DEFAULT 0,
    bounced_emails INT DEFAULT 0,
    spam_reports INT DEFAULT 0,
    domain_registered_date DATE,
    is_whitelisted BOOLEAN DEFAULT FALSE,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    last_seen TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE attachment_cache (
    sha256 VARCHAR(64) PRIMARY KEY,
    filename VARCHAR(255),
    mime_type VARCHAR(100),
    extension VARCHAR(10),
    risk_score INT,
    virustotal_result JSONB,
    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE url_cache (
    url_id VARCHAR(255) PRIMARY KEY,
    url TEXT NOT NULL,
    risk_score INT,
    risk_level VARCHAR(20),
    virustotal_result JSONB,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    alert_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID REFERENCES emails(message_id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    severity VARCHAR(20) CHECK (severity IN ('HIGH', 'MEDIUM', 'LOW')),
    threat_type VARCHAR(50),
    sender_email VARCHAR(255),
    subject VARCHAR(1000),
    action_taken VARCHAR(20),
    threat_indicators TEXT[],
    recommendation TEXT,
    dismissed_at TIMESTAMP
);

CREATE TABLE audit_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user VARCHAR(255) NOT NULL DEFAULT 'system',
    action VARCHAR(50),
    target_email_id UUID REFERENCES emails(message_id),
    changes JSONB,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_emails_sender ON emails(sender_email);
CREATE INDEX idx_emails_timestamp ON emails(timestamp_received DESC);
CREATE INDEX idx_threat_composite ON threat_analysis(composite_threat_score DESC);
CREATE INDEX idx_decisions_type ON decisions(decision);
CREATE INDEX idx_alerts_severity ON alerts(severity);

-- Seed Data
INSERT INTO sender_reputation (sender_domain, reputation_score, is_whitelisted)
VALUES 
('gmail.com', 85, TRUE),
('microsoft.com', 90, TRUE),
('company.com', 95, TRUE)
ON CONFLICT DO NOTHING;
