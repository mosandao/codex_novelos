ALTER TABLE creator_profiles ADD COLUMN ownership TEXT NOT NULL DEFAULT 'user' CHECK (ownership IN ('system_archetype', 'user'));

CREATE INDEX idx_creator_profiles_ownership ON creator_profiles(ownership);
