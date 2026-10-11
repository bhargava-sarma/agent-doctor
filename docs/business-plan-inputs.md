# Agent Doctor: business plan inputs for cfo.ai

## Product, in one line
Self-healing for AI agents. Agent Doctor reads an agent's traces, finds the root cause of failures, patches the code, and opens a PR only when re-run traces prove the fix worked.

## Customer
- **Primary:** engineering teams running LLM agents in production (AI-native startups, 5–50 engineers) who already collect traces but have nobody with time to read them.
- **Secondary:** platform/ML teams at mid-size companies running 10+ internal agents.
- **Distribution:** an integration inside observability tools (neatlogs first), GitHub Marketplace app, open-source CLI as top of funnel.

## Pricing
The hook: **you pay for verified fixes, not attempts.** A heal that doesn't verify against the traces isn't counted.

| Plan | Price | Included | Who |
|---|---|---|---|
| Free | $0 | 20 verified fixes/month, 1 agent, CLI only | individual devs, OSS |
| Pro | $99/month | 250 verified fixes, 5 agents, auto-PR | small teams |
| Team | $499/month | 2,000 verified fixes, unlimited agents, CI auto-heal on failing evals, Slack alerts | growing AI teams |
| Enterprise | from $2,500/month | self-hosted / bring-your-own-model, SSO, audit log | larger companies |

Overage: $0.50 per verified fix above the plan's allowance.

## Unit economics (measured during the hackathon)
- LLM cost per healing run: **≈ $0.18** (patient re-runs on Claude Haiku + 3 diagnosis rounds on Claude Sonnet). Measured: $0.79 total across ~5 full runs.
- Budget assumption: **$0.25 per run** to cover larger agents and retries.
- Hosting/infra: $300/month (workers, queue, DB) for the first year.
- Gross margin target: ~75% (Pro at full allowance = $62 LLM cost on $99; typical usage is ~40% of allowance).

## Costs (monthly)
| Item | Months 1–6 | Months 7–12 |
|---|---|---|
| Founders (3, India, stipends) | $4,500 | $7,500 |
| Infrastructure | $300 | $800 |
| LLM cost (COGS) | 25% of revenue | 25% of revenue |
| Tools & SaaS | $200 | $400 |
| Marketing (content, launches, events) | $500 | $2,000 |
| First hire (developer relations, from month 9) | – | $2,500 |

## Revenue assumptions (customers at end of month)
| Month | Pro | Team | Enterprise | MRR |
|---|---|---|---|---|
| 1 | 0 | 0 | 0 | $0 |
| 3 | 10 | 0 | 0 | $990 |
| 6 | 40 | 5 | 0 | $6,455 |
| 9 | 80 | 12 | 1 | $16,408 |
| 12 | 120 | 25 | 2 | $29,355 |

Churn: 4%/month on Pro, 2% on Team. Free→Pro conversion: 4%.

## Funding
- Starting cash: $25,000 (founders + hackathon prize money and credits)
- Planned pre-seed raise: $250,000 in month 6
- Goal: default-alive (MRR covers costs) by month 10–12.

## Questions for cfo.ai to answer
1. Runway with and without the month-6 raise.
2. Break-even month.
3. Sensitivity: what if LLM cost per run doubles, or Pro conversion is 2% instead of 4%?
