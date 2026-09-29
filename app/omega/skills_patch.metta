; Add to Omega (singnet/Omega) per docs/tutorial-03-writing-a-custom-skill.md
; Step 1: add this line inside the getSkills list in src/skills.metta:
;   "- Resolve two disagreeing agents' claims with auditable MeTTa reasoning: (negotiate scenario_id_or_text_in_quotes)"
; Step 2: add this definition in src/skills.metta:
(= (negotiate $arg) (py-call (twoagents_bridge.negotiate $arg)))
; Step 3: copy twoagents_bridge.py where Omega's python bridges live, export TWOAGENTS_HOME, restart, ask:
;   "have the two agents resolve the crop scenario"  -> LLM should emit (negotiate "crop")
; UNVERIFIED against a running Omega: confirm the py-call module path with the mentors (docs/reference-python-bridges.md).
