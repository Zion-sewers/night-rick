# Judge Replacement Testing — Field Notes

*Distilled field notes: statistical machinery for deciding when an LLM judge may replace human annotators. Mechanisms described in plain language for operational use. No source text reproduced.*

---

## 1. What the work actually proposes

A statistical procedure that answers one question with a yes or no: may this LLM judge replace human annotators on this task? Instead of the usual approach (measure agreement with majority-vote labels and squint at whether 0.8 is good enough), it runs a leave-one-out contest: each human annotator is removed in turn, and the LLM and the removed annotator are both scored on how well they match the remaining humans. A cost-benefit penalty is baked into the hypothesis test to reflect that the LLM is cheaper, false-discovery control is applied across the per-annotator comparisons, and the LLM passes only if it beats a majority of the humans. Alongside the test it introduces a single interpretable number, the advantage probability: the probability that the LLM's annotations are as good as or better than those of a randomly chosen human annotator. The headline empirical finding is that replacement is sometimes justified but highly task- and aspect-dependent, and that the test itself, not any particular model ranking, is the contribution.

---

## 2. Core mechanisms

### M1. Leave-one-out replacement contest

**How it works, step by step:**
1. Take a modest labeled sample (50 to 100 instances), each labeled independently by at least three human annotators.
2. Remove one annotator. Score the LLM on how well its labels match the remaining annotators' labels. Score the removed annotator the same way against the same remaining group.
3. Repeat for every annotator. Each round is a head-to-head: does the LLM represent the group better than this particular human does?
4. This reframes the question correctly. Traditional metrics ask "does the LLM agree with the consensus," which flatters any model that parrots the majority. The contest asks "is the LLM a better stand-in for a randomly hired annotator than the actual humans are."

**Illustration:** On a climate-article framing task with four annotators, every tested LLM beat all four humans; on a conversation-comparison benchmark with three expert annotators, no LLM beat any of them. Same models, opposite verdicts — the test is measuring the task's replaceability, not just the model's strength.

**Apply it:** Before replacing any human label flow with a judge, run this contest on a 50–100 instance calibration set. If the LLM cannot beat the humans you already employ, it has no business replacing them.

### M2. Advantage probability — one number that means something

**How it works, step by step:**
1. For each instance and each removed annotator, record a binary win: 1 if the LLM's alignment score meets or beats the removed annotator's, 0 otherwise.
2. Average these wins across instances to get the per-annotator advantage probability: the estimated chance the LLM is at least as good as that annotator.
3. Average across annotators. The result is a number between 0 and 1 with a plain reading: the probability the LLM's labels are as good as or better than those of a randomly chosen human annotator.
4. It works unchanged across label types: accuracy-style scoring for discrete labels, negative error for continuous scales, similarity scoring for free text.

**Illustration:** A judge can show 0.80 accuracy against majority vote yet carry an advantage probability of only 0.55 — meaning it looks strong against the flattened consensus but is barely better than a coin flip against individual humans. The two numbers diverge exactly when individual annotators disagree with each other, which is when the choice of metric matters most.

**Apply it:** Report advantage probability alongside (or instead of) accuracy and F1 in every judge evaluation. It is the number that answers the hiring question: would I rather have this model or a random analyst?

### M3. Cost-benefit penalty inside the hypothesis test

**How it works, step by step:**
1. The LLM is cheaper and faster than a human. A fair replacement test should not demand strict superiority; it should demand superiority net of the cost advantage.
2. This is formalized as a penalty term subtracted from the human's side in each per-annotator hypothesis test: the LLM wins the round if its advantage probability significantly exceeds the human's minus the penalty.
3. The penalty is set by annotator cost: higher for expensive experts, lower for cheap crowd workers. The recommended scale runs from 0.1 (crowd) through 0.15 (skilled) to 0.2 (experts).
4. A larger penalty means the test passes more easily — which is correct, because replacing an expensive expert panel is worth more than replacing cheap crowd labor.

**Illustration:** With the penalty at 0.2, most passing judges clear the bar before 100 annotated instances; at 0.1, the same comparisons typically need 100–150. The penalty is doing real work: it encodes how much imperfection you will tolerate in exchange for scale.

**Apply it:** Set the penalty explicitly from your annotator economics and document it. An undocumented threshold is a fudge factor; a documented one is a policy.

### M4. False-discovery control across annotators

**How it works, step by step:**
1. The procedure runs one hypothesis test per annotator. With many annotators, some wins will happen by luck.
2. A false-discovery-rate controlling procedure (the variant designed for dependent hypotheses, since the per-annotator tests share data) is applied to the set of p-values.
3. Only rejections that survive the correction count toward the winning rate. The standard target is a 5% false-discovery rate.

**Illustration:** Without correction, a judge tested against 13 annotators could rack up lucky wins and look replaceable; with correction, only robust wins survive. This is what separates the procedure from "count how many annotators the model beats."

**Apply it:** Never report raw per-annotator win counts as evidence. Always correct for multiple comparisons, especially when your annotator pool is large.

### M5. Winning-rate decision rule — a clear gate

**How it works, step by step:**
1. After correction, count the fraction of annotators the LLM significantly beats. This is the winning rate.
2. The decision rule is fixed: winning rate at or above one half means the LLM beats the majority of the humans, which justifies replacement.
3. The threshold is a hyperparameter. One half is the default; high-stakes domains should demand stricter values.

**Illustration:** On a restaurant-review sentiment task, nearly every tested model cleared the bar; on a summary-quality task, none did. The gate is not grading models on a curve — it is certifying task instances as replaceable or not.

**Apply it:** Wire this gate into your judge-promotion pipeline: no judge goes to production on a new task family without clearing the winning-rate bar on a calibration set. Raise the bar for compliance-critical decisions.

### M6. The optimal judge is embarrassingly simple

**How it works, step by step:**
1. For discrete labels scored by agreement, the theoretically optimal judge — the one that maximizes advantage probability — simply predicts the majority vote on each instance.
2. For continuous scores, the optimal judge predicts the mean of the annotators' scores.
3. Both achieve the maximum possible advantage probability. No clever prompting can beat them in expectation on these scoring rules.

**Illustration:** This is why few-shot prompting helps judges: the demonstrations pull the model's output distribution toward the human distribution's center, approximating the majority/mean predictor. Chain-of-thought reasoning, which moves the model away from the distributional center toward its own reasoning path, does not help and often hurts.

**Apply it:** When distilling or fine-tuning a judge, the majority vote (discrete) or mean score (continuous) is the correct training target, not any individual annotator's labels. If your judge systematically deviates from the consensus center, that is a defect, not independence of thought.

### M7. Aspect-level decomposition — aggregates hide failures

**How it works, step by step:**
1. Run the replacement test separately for each annotation aspect (e.g., coherence vs. factual consistency of a summary; color vs. shape features of an image).
2. Judge quality varies dramatically by aspect. A model can clear the bar on easy aspects and fail the ones that matter.
3. The failure aspects are predictable: they are the ones requiring the capabilities the model lacks — spatial reasoning, emotional intelligence, deep context.

**Illustration:** On a skin-lesion task, every model passed on color-related aspects (counting colors, spotting glow) and struggled on shape aspects (asymmetry, border irregularity). On an emotional-support task, all models excelled at rating sensitivity while failing aspects needing genuine emotional understanding. An aggregate score would have hidden both splits.

**Apply it:** Never certify a judge on an aggregate score alone. Decompose by aspect, and require the aspects that drive your risk decisions to pass independently. Your fraud judge may be excellent at fluency and terrible at the one aspect that catches money laundering.

### M8. Prompting levers that actually move judge quality

**How it works, step by step:**
1. Few-shot prompting (a handful of demonstrations with reference labels) consistently improves judge quality — it aligns the model's scoring distribution with the humans'.
2. Chain-of-thought prompting degrades judge performance in nearly half of tested configurations. Reasoning step by step helps problem-solving; for judgment it adds variance without adding signal.
3. Ensembling multiple models or strategies does not beat the best single few-shot judge.

**Illustration:** On a summary-evaluation task where no zero-shot judge passed the replacement test, adding four demonstrations pushed two models over the bar. The same models with chain-of-thought stayed below it.

**Apply it:** Spend your prompt-engineering budget on demonstration selection, not on reasoning scaffolds or ensembles. For judge pipelines, demonstrations are the lever; everything else is decoration.

### M9. Noisy humans fail the test — and that is a feature

**How it works, step by step:**
1. When human annotators disagree heavily (untrained workers, vague guidelines, inherently subjective tasks), the leave-one-out contest produces high-variance comparisons.
2. High variance means the hypothesis tests rarely reject — the LLM cannot demonstrate a stable advantage over any individual when the group itself is incoherent.
3. So the test fails. This is correct behavior: if your humans cannot agree, you have an annotation-process problem, and no judge — human or machine — should be certified on that task.

**Illustration:** The procedure's failure mode doubles as a process diagnostic. A task where no judge passes and inter-annotator agreement is low is telling you to fix the guidelines or the annotator selection, not to shop for a better model.

**Apply it:** When a judge fails certification, check inter-annotator agreement before blaming the model. Low agreement means the task definition is the problem. Fix the rubric, retrain the analysts, then re-run the contest.

### M10. The weak-annotator loophole and its guard

**How it works, step by step:**
1. The test compares the LLM against the annotators you supply. If you supply weak, inconsistent annotators, even a mediocre LLM looks good by comparison.
2. No statistic can fully prevent this misuse — comparing against strawmen is a choice, not an estimation error.
3. The guard is transparency: publish the annotator profiles, the guidelines, and the human labels themselves, so reviewers can judge whether the humans were worthy opponents.

**Illustration:** In the single-expert variant, the LLM and a set of non-experts are both tested against one trusted expert. If the non-experts are unqualified, the LLM's apparent win says nothing. The procedure is only as honest as its human baseline.

**Apply it:** Treat the human baseline as part of the certification artifact. Document who the annotators were, their expertise, and the guidelines. A judge certified against weak humans is not certified at all. For analyst-label de-noising pipelines, this means: certify against your best analysts, not your noisiest queue.

---

## 3. Popular take vs the book's sharper argument

**The popular take:** "LLMs can replace human annotators — the study proves it across ten datasets."

**Where it is wrong or shallow:**

1. **The finding is conditional, not general.** Replacement was justified on some datasets and flatly rejected on others, and within datasets it varied by aspect. The honest headline is not "LLMs can replace humans" but "replaceability is a property of the task, measurable with 50–100 labeled instances" — and most teams are currently deploying judges without ever measuring it.
2. **Chain-of-thought does not help judges.** The folk wisdom that reasoning scaffolds improve everything fails here: for judgment tasks, chain-of-thought added variance without signal in nearly half the configurations, while four plain demonstrations reliably helped. The mechanism is distributional alignment, not reasoning depth.
3. **Accuracy against majority vote is the wrong metric.** It flatters models that parrot the consensus and cannot distinguish "matches the flattened label" from "would be a good replacement hire." The leave-one-out contest is asking the economically relevant question; accuracy is answering a different one.

---

## 4. Strongest steelmanned objection

**The objection:** The entire procedure validates the LLM against human consensus, so it can only ever certify "as good as the average human" — it is blind to the case where the LLM is right and all the humans share a systematic blind spot. Worse, the cost-benefit penalty is a tunable dial: pick a larger value and more judges pass, so the "statistical rigor" is partly theater around a subjective threshold. Add data contamination (public benchmarks may be in the models' training data, inflating agreement) and the procedure starts to look like a sophisticated way to rubber-stamp a decision the team already made.

**Does it hold?** Partially, and the partial failure is instructive. The ceiling critique is real: the base procedure cannot certify superhuman judgment, only human-parity — the authors relegate "does the LLM outperform humans" to an extension, which concedes the point. The contamination caveat is genuine for public benchmarks and should discount any passing result on them. But the penalty-as-theater charge misunderstands the design: an explicit, documented penalty is strictly better than the status quo, where teams pick an accuracy threshold by gut feel and never write it down. The procedure's real value is not the verdict but the discipline — a fixed protocol, a documented penalty, corrected comparisons, and published baselines. Treat a pass as "certified human-parity on this aspect set," never as "the judge is right," and the objection becomes a usage manual rather than a refutation.

---

## 5. Practitioner's checklist

1. **Run the contest before replacing:** 50–100 instances, at least 3 independent annotators per instance, before any judge replaces a human label flow.
2. **Contest, don't correlate:** compare the LLM against each annotator via leave-one-out, not against majority-vote labels alone.
3. **Report advantage probability:** the chance the judge is at least as good as a randomly chosen human annotator — the number that answers the hiring question.
4. **Set the cost penalty explicitly:** 0.2 for expensive experts, 0.15 for skilled annotators, 0.1 for crowd workers; document the choice.
5. **Correct for multiple comparisons:** false-discovery control across per-annotator tests, or lucky wins will certify bad judges.
6. **Gate on winning rate ≥ 0.5:** the judge must beat the majority of your humans; raise the bar for compliance-critical decisions.
7. **Decompose by aspect:** certify each risk-relevant aspect independently; aggregates hide the failures that matter.
8. **Few-shot with ~4 demonstrations:** the highest-ROI prompt lever for judges; pick demonstrations that pin the scoring distribution.
9. **Skip chain-of-thought for judgment:** it adds variance without signal on rating and classification tasks.
10. **Don't ensemble for quality:** ensembles don't beat the best single few-shot judge; spend the budget on calibration data instead.
11. **Read failures as process diagnostics:** if no judge passes and humans disagree, fix the guidelines and retrain analysts before shopping for models.
12. **Certify against your best humans:** a judge validated against weak annotators is not validated; publish annotator profiles and labels.
13. **Handle imbalance explicitly:** on skewed label distributions, adjust the scoring so the majority class doesn't dominate the verdict.
14. **Protect minority opinions:** on subjective tasks, add an explicit mechanism for minority judgments rather than letting the contest flatten them.
15. **Remember the ceiling:** the procedure certifies human-parity, not superhumanity — and discount passes on public benchmarks for possible training-data contamination.

---

*Coverage note: the appendices on proofs, dataset details, and prompt templates are reference material with little transferable content beyond what is distilled above. The single-expert and annotator-quality extensions are useful but secondary; the core contribution is the contest plus the advantage-probability measure.*
