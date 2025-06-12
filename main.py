from recruitment_agent import recruiter, State
from onboarding_agent import onboarder, OnboardingState

if __name__ == "__main__":
    accepted_candidates = recruiter(State)

    if accepted_candidates:
        print(f"✅ {len(accepted_candidates)} candidate(s) accepted. Running onboarding agent...")
        onboarder(OnboardingState)  # you can modify to run per-candidate if needed
    else:
        print("❌ No candidate accepted. Skipping onboarding.")
