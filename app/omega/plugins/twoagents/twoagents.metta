; Omega plugin: exposes the two-agent negotiation as a skill (see Omega docs/reference-plugin-api.md)
(= (loadOmegaPlugin)
   (progn
     (add-skill negotiate "Resolve two disagreeing claims about one fact. Two agents with different evidence lenses negotiate via MeTTa rules and return a resolution plus reasoning trace. Argument: a scenario id (crop, campus, tie) or text in line format" (conflict_text_in_quotes))
     ()))
(= (negotiate $arg) (py-call (twoagents_bridge.negotiate $arg)))
