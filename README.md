# Imbue Catalyst AI Scientist

A tool for semi-autonomous scientific research and discovery.

![Catalyst Logo](src/assets/catalyst-small.png)

### What Imbue Catalyst Can Do

Imbue Catalyst supports two core research modalities:
1. **Explaining Phenomena**: Autonomously develops a theory to explain an observed phenomenon. It also supports taking a user-provided theory draft, filling in gaps, and auto-correcting mistakes and oversights.
2. **Verifiable Goal Solving/Optimization**: Autonomously solves a research goal that can be verified through code, or optimizes a measurable metric.

In addition to these high-level workflows, Imbue Catalyst provides a menu of pre-defined manual operations (add-on steps) such as reviewing a theory for correctness, proposing refinements, or evaluating solution candidates.

### Suitable Problems

#### 1. Explaining Phenomena
This modality helps develop explanations for observable phenomena. Suitable problems are typically of the shape:
* "When we do Y, we observe X. What is the mechanism that causes X?"
* "We sometimes see X while doing Y. Under what conditions does X happen, and why?"
* "Explain what happens when we do X."

In short, it aims to answer "Why" questions that lead to testable predictions.

The current implementation of Imbue Catalyst is designed to work for phenomena that can be understood through computational experiments and mathematical derivation. Our testing so far has been limited to phenomena in the field of machine learning / deep learning theory in particular.

You will have a higher chance of success *if*:
* The phenomenon is described precisely and with little room for interpretation
* You're able to provide simplifying assumptions or limit the scope of the investigation upfront. E.g. "Only consider linear networks with the following loss function: ..."
* The phenomenon can be reproduced and probed through programmatic experimentation (i.e. run by a Python script on your computer).
* You can describe the *shape* of the explanation that you are looking for.

#### 2. Verifiable Goal Solving/Optimization
This modality is designed to find a concrete solution to a specified research goal that can be validated programmatically. Suitable problems are of the shape:
* "Find a configuration or function that fulfils condition X under verification script Y."
* "Find an implementation that maximizes metric X as measured by method Y."
* "Optimize the training speed of model A without dropping accuracy below B."

### What Imbue Catalyst is Not a Good Fit For

Imbue Catalyst is *not* a good fit for:
* Unstructured or unconstrained optimization problems that lack clear programmatic verification criteria (e.g. "make my model better" without a specified metric or verification script)
* Problems with subjective or under-specified success criteria, e.g. "develop a theoretical framework for overfitting in deep learning"
* Engineering problems, e.g. "build an operating system for microcontrollers", "design an efficient HTML rendering engine"
* Problems that are significantly out of reach for the underlying base model, e.g. "Prove or disprove P=NP", "Unify quantum physics and general relativity into a practically testable theory of everything"
* Problems that require experiments that can't be run on a computer (life sciences, psychology, experimental physics, etc.)
* Problems that require significant computational resources to solve. Imbue Catalyst limits the runtime of any single experiment to 30 minutes by default (though this is adjustable via `CATALYST_EXPERIMENT_TIMEOUT_SECS`). Furthermore, only the verifiable goal workflows presently make any attempt to optimize for experiment efficiency at all.

### Why Choose Imbue Catalyst Over a Bare LLM Chat or Coding Agent?

Imbue Catalyst does not replace LLM Chat interfaces or off-the-shelf coding agents. Those remain a better fit for interactive, conversational exploration of a topic, and for any problems that don't fit the criteria mentioned above.

While Imbue Catalyst is built on top of those same LLMs, it adds unique techniques that allow it to produce results beyond the capabilities of the raw model and harness:

* Imbue Catalyst implements adversarial review-refinement loops: One set of agents continuously improves the generated theory or solution candidate, while separate, independent agents are tasked with falsifying its statements, identifying edge cases, and highlighting its limits.
* Imbue Catalyst deploys an evolution-inspired system to build a population of competing theories or solution candidates. The candidates are repeatedly ranked against each other and checked against empirical data/verification scripts. The most promising candidates are selected for further refinement and branching.


## Getting Started

1. Before using Imbue Catalyst, carefully review the "Supported Models & Estimated Costs" section below.
2. `git clone https://github.com/imbue-ai/catalyst.git && cd catalyst`
3. `git checkout stable` to use the stable branch
4. Install [prerequisites](src/README.md#prerequisites)
5. `cd src && ./run.sh`
6. Follow the [Quickstart Guide](src/docs/quickstart.md) for next steps.

## Supported Models & Estimated Costs

Imbue Catalyst utilizes an existing agentic harness installed on your system. It currently supports the following harnesses:
* Claude Code (either via `claude -p` or via [mngr](https://github.com/imbue-ai/mngr))
* Gemini CLI (via `gemini -p`)
* Antigravity CLI (via `agy -p`)
* Codex CLI (via `codex exec`)

Token usage will be billed directly by the provider (Anthropic, Google, or OpenAI), based on the harness' existing authentication.

Before using Imbue Catalyst, please familiarize yourself with the expected costs listed below. **The evolution-based workflows in particular are frequently composed of >100 subagents, and can incur significant token usage.**

> [!TIP]
> About 65% of tokens in a typical Develop Theory workflow are used for review & scoring steps, 25% for theory/solution development, and 10% for miscellaneous. **You can reduce your cost by configuring "Step Type Model Overrides"**, and using the strongest model only for development steps. Review & scoring and miscellaneous steps can often work with a slightly weaker model without significantly impacting the quality of your results.

The costs shown below are rough estimates (order of magnitude), and will vary **significantly** depending on your research task. Even when using a subscription, extra charges may apply after you exhaust your plan's rate limits depending on your configuration (Anthropic Usage Credits, Gemini AI Credits etc.). **Please monitor your provider's spend dashboard to avoid unwanted surprises.**

| Harness | Can use subscription plan? | Runs in sandbox | Model | Cost per "Develop Theory (Evolution)" | Cost per "Solve Verifiable Goal (Evolution)" | Cost per "Develop Theory (Linear)" | Cost per manual step |
| -- | -- | -- | -- | -- | -- | -- | -- |
| **Claude Code**  | Yes, Max 20x recommended | Yes | Opus 4.8 | included in subscription; ~$1,000 USD when using API billing | included in subscription; ~$500 USD when using API billing | included in subscription; ~$200 USD when using API billing | included in subscription; ~$20 USD when using API billing |
| | | | Sonnet 4.6 | included in subscription; ~$500 USD when using API billing | included in subscription; ~$250 USD when using API billing | included in subscription; ~$100 USD when using API billing | included in subscription; ~$10 when using API billing |
| | | | Haiku 4.5 | included in subscription; ~$150 USD when using API billing | included in subscription; ~$75 USD when using API billing | included in subscription; ~$30 USD when using API billing | included in subscription; ~$3 USD when using API billing |
| **Gemini CLI** | No | Yes | 3.5 Flash | ~$200 USD | ~$100 USD | ~$40 USD | ~$4 USD |
| | | | 3.1 Pro | ~$300 USD | ~$150 USD | ~$60 USD | ~$6 USD |
| | | | 3 Flash | ~$100 USD | ~$50 USD | ~$20 USD | ~$2 USD |
| **Antigravity CLI** | Yes, AI Ultra recommended | [No](https://github.com/google-antigravity/antigravity-cli/issues/286) | 3.5 Flash | included in subscription; ~$200 USD when using API billing | included in subscription; ~$100 USD when using API billing | included in subscription; ~$40 USD when using API billing | included in subscription; ~$4 USD when using API billing |
| | | | 3.1 Pro | included in subscription; ~$300 USD when using API billing | included in subscription; ~$150 USD when using API billing | included in subscription; ~$60 USD when using API billing | included in subscription; ~$6 USD when using API billing |
| **Codex CLI** | Yes, Pro 20x recommended | Yes | GPT 5.5 | included in subscription; ~$500 USD when using API billing | included in subscription; ~$250 USD when using API billing | included in subscription; ~$100 USD when using API billing | included in subscription; ~$10 USD when using API billing |


## Further Documentation

Additional information can be found in the following guides:

- [Setup](src/README.md): Prerequisites, setup & troubleshooting instructions.
- [Quickstart Guide](src/docs/quickstart.md): An overview of the system structure and how to run you research.
- [Mid-Research Steering](src/docs/steering.md): How to steer the direction of an ongoing research task
- [Workflows and Add-ons](src/docs/workflow.md): A reference for all primary workflows and individual add-on steps.
- [CLI Agent Usage](src/docs/cli.md): Instructions for using AI Scientist skills directly within a CLI agent.

## Contributors

Imbue Catalyst is built by your friends at [Imbue](https://imbue.com):

* [Daniel Mewes](https://github.com/danielmewes/)
* [Catherine Kim](https://github.com/catherinek07/)
* [Evan Ryan Gunter](https://github.com/evgunter)
