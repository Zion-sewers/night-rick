# Field Notes: Financial Statement Mechanics, Ratios, and Manipulation

These notes distill a step-by-step teaching book on financial statements: it builds a manufacturing startup's books transaction by transaction, then covers valuation, ratio analysis, alternative accounting policies, and fraud. What it actually teaches is the mechanics of the system: how a single business event lands on three statements at once, where the legal judgment calls sit, and which of those judgment calls double as fraud tools. The core lesson for a risk reader is that financial statements are not facts about a company. They are the output of a rule engine with configurable parameters, and reading them fluently means knowing exactly which parameters management chose and when they changed them.

---

## 1. Accrual accounting: profit is a timing decision, not a cash event

**How it works, step by step.** Under accrual accounting, revenue is recorded when the economic work is done, not when cash arrives. An order changes nothing. A sale is booked when the product ships, the customer owes payment, and the company has no significant remaining obligation. Costs are recorded in the same period as the matching revenue. Costs that are not tied to a product (salaries, legal, insurance) are allocated to the period by some systematic rule, or recorded when they arise as period expenses.

**Concrete illustration.** The company ships 15,000 cases to a retailer on credit for $234,900. The income statement immediately records the full sale plus the associated cost of goods, and profit rises. The balance sheet records a $234,900 accounts receivable. Cash does not move. Weeks later, when the customer pays, cash rises and receivables fall, but the income statement is untouched. The sale happened once; the cash is a separate event.

**Analyst application.** Any time profit and cash diverge, this is the first mechanism to check. A growing company can be wildly profitable on paper while bleeding cash, because credit sales and inventory build-up sit in working capital, not in the cash register. The cash flow statement exists precisely to bridge this gap: start from net income, add back non-cash charges, then adjust for changes in receivables, inventory, and payables. Run that bridge yourself. If operating cash flow trails net income quarter after quarter, the profit is being funded by the balance sheet, and you want to know exactly which line is absorbing it.

---

## 2. The cost-vs-expense divide: where manufacturing costs hide

**How it works, step by step.** Costs go into the product and sit in inventory on the balance sheet. Expenses hit the income statement immediately. When the factory pays wages, buys raw material, books depreciation, or pays overhead, nothing touches profit. Those amounts accumulate in inventory (raw material, work-in-process, finished goods). Only when the finished product ships do the accumulated costs leave inventory and become cost of goods sold on the income statement. SG&A (sales, general, administrative) is different: it is always an expense, hitting the income statement the month it is incurred.

**Concrete illustration.** The company buys a building for $1.5 million. No income statement effect; cash falls, fixed assets rise. Each month, a $7,143 depreciation charge on that building is added to work-in-process inventory, not expensed. Profit is untouched that month. Months later, when the sauce made in that building is sold, the depreciation finally surfaces inside cost of goods sold.

**Analyst application.** This is the single biggest reason early-year profits of a capital-heavy company look better than the economics. A large asset purchase flatters current earnings; the pain is amortized into the future. For risk work, watch the classification line: anything management moves from "expense" to "capitalized cost" pushes profit from today into tomorrow's balance sheet. Ask what is accumulating in inventory and other assets that used to flow straight through the income statement.

---

## 3. Depreciation: the non-cash charge that still cuts profit

**How it works, step by step.** Depreciation allocates a fixed asset's cost across its useful life. No cash changes hands when depreciation is booked. It reduces net income (through cost of goods or operating expense, depending on the asset) and reduces the asset's net book value via the accumulated depreciation contra-account. The income statement shows an expense; the cash flow statement adds it back.

**Concrete illustration.** In the worked year, the company records $78,573 in accumulated depreciation against $1.75 million of assets. Net income is $251,883. On the cash flow bridge, that $64,287 of the year's depreciation is added back to net income to approach operating cash. The company never wrote that check; it was charged for using machines it already owns.

**Analyst application.** Depreciation is the cleanest place to see the profit/cash split, and also a quiet earnings lever. Lengthening an asset's useful life spreads the same cost over more years, lifting reported profit every year with zero change in the business. Compare depreciation periods across years and across peers. A company that quietly extends useful lives while capital expenditure stays flat is manufacturing margin out of accounting assumptions.

---

## 4. Working-capital buffers: receivables, inventory, payables as shock absorbers

**How it works, step by step.** Three accounts sit between the income statement and cash: receivables (sales you have not collected), inventory (costs you have not sold), and payables (expenses you have not paid). When receivables grow, profit is ahead of cash. When payables grow, cash is ahead of profit. These are legitimate timing differences, but they are also where deteriorating businesses hide first, because the income statement keeps looking fine while the buffers absorb the damage.

**Concrete illustration.** The company's terms are net 30, meaning payment is due within 30 days of shipment. Its receivables stand at 54 days of sales. One customer goes bankrupt entirely; the $15,900 receivable is written off as a bad-debt expense, and the earlier $5,382 profit booked on that sale reverses into a $10,200 net loss (the inventory value of the goods). Meanwhile inventory behavior is its own tell: when sales slow, finished goods pile up and the inventory turn ratio drops, signaling trouble before it reaches the income statement.

**Analyst application.** Compute days-sales-outstanding (receivables relative to sales) and watch the trend, not the level. A company extending its own payment terms or failing to collect shows up here first. Same for inventory days and payables days. Then ask whether the pattern is healthy or strained: a fast-growing company legitimately soaks up working capital, but a company whose DSO stretches while revenue is flat is booking sales it cannot collect. The book's rule of thumb is blunt and useful: profit and liquidity are different things, and a profitable company can still run out of cash.

---

## 5. Legal cosmetics: the policy table management chooses from

**How it works, step by step.** Within the accounting rules, management picks policies that shift profit between periods, entirely legally. The main levers: revenue recognition (book at sale vs after the buyer carries all risk), inventory valuation (FIFO assigns oldest costs to goods sold; LIFO assigns newest), depreciation speed (accelerated books cost faster), reserve and allowance levels (low warranty and bad-debt reserves flatter current profit), contingent liabilities (footnote only vs accrue the loss now), and whether marketing or development spending is capitalized (asset, written off later) or expensed (hit now). In a period of rising costs, FIFO produces lower cost of goods, higher profit, and a higher tax bill than LIFO.

**Concrete illustration.** Two identical companies with identical physical operations report different profits and different inventory values purely because one uses FIFO and the other LIFO. Both are "correct" under the rules.

**Analyst application.** This is the legal half of the manipulation playbook, and it matters because the line between it and fraud is intent, not mechanics. The single most important check: did the company change policies, and in which direction? A switch from LIFO to FIFO, from expensing to capitalizing marketing, or from fast to slow depreciation is a red flag regardless of the justification offered. Conservative policies (high reserves, fast depreciation, expense everything) produce profits you can trust; aggressive policies produce profits you should discount. And never compare two companies' profits without checking that they use the same policies first.

---

## 6. Revenue recognition games: booking the sale before it is real

**How it works, step by step.** Revenue should be recorded only when an order exists, the product has shipped, the customer is likely to accept it, no significant company action remains, and title has transferred with the buyer's acknowledged obligation to pay. Each condition is a judgment call, and each can be bent: recording sales before shipment completes, shipping to yourself or an affiliate (self-dealing), easing acceptance-risk standards, or booking revenue where substantial follow-up work remains.

**Concrete illustration.** The worked example ships goods to a shaky related-party buyer on credit, books the full sale and profit, and only later writes off the entire receivable when the buyer goes bankrupt. The profit was real on paper for months.

**Analyst application.** Cross-check revenue growth against receivables growth and against cash collected from customers. If receivables are growing much faster than revenue, the company is either extending credit aggressively or booking sales on thin ice. Look for round-trip patterns (sales to entities that also buy from the company), end-of-quarter shipment spikes, and any relaxation of stated revenue policies in the footnotes. A genuine sale turns into cash; a manufactured one turns into a write-off.

---

## 7. The asset-swap gain: one-time profit dressed as operating strength

**How it works, step by step.** A company owns an asset carried on the books at depreciated historical cost, far below its market value. It sells the asset, books the difference as a gain, and buys a similar replacement asset at market price. Economically nothing changed: same warehouse, less cash (after transaction costs and taxes). But the income statement shows a large gain, and if that gain is presented inside operating income, the company's recurring earning power is overstated.

**Concrete illustration.** An old warehouse carried at $500,000 sells for $5 million. The company books a $4.5 million gain, then buys a similar warehouse for $5 million. It now holds essentially the same facility, has less cash than before, paid tax on the gain, and reports $4.5 million of "profit" that will never repeat.

**Analyst application.** Separate recurring from non-recurring income every time. Read the income statement from the top down: sales, cost of goods, operating expenses give you the business; everything below or around those lines (asset sales, one-time gains, "other income") is suspect until proven otherwise. If operating income contains capital gains, the company has cooked its books even if every number is technically legal. For risk work, ask: what would earnings look like with every non-recurring item stripped out, and would the company still clear its debt covenants?

---

## 8. Ratio analysis: relationships, not numbers, and only against a benchmark

**How it works, step by step.** Ratios compare two statement numbers to expose a relationship: liquidity (can bills be paid: current ratio of current assets to current liabilities; quick ratio excluding inventory), asset management (how hard assets work: inventory turns, receivables days, asset turnover), profitability (gross margin, return on sales, return on assets, return on equity), and leverage (debt-to-equity, debt-to-assets). Common-size statements restate every line as a percentage of sales (income statement) or total assets (balance sheet) so structure, not scale, is visible.

**Concrete illustration.** The example company shows an 8% return on sales and 15% return on equity, which sound healthy, while its return on assets is a low 8% and its receivables run at 54 days against 30-day terms. Industry comparisons reframe everything: a grocery chain earns a penny of profit per dollar of sales while a software company earns a quarter; a restaurant turns inventory 90 times a year while a manufacturer turns it twice. Same ratio, different universe.

**Analyst application.** A ratio without a benchmark is decoration. Compare three ways: against the company's own history (are receivable days lengthening? is gross margin eroding?), against a direct competitor, and against industry norms. For risk, the leverage ratios matter most: debt-to-equity shows the equity cushion available to absorb losses, and a high ROE built on debt rather than asset returns is fragile by construction. Also note what ratios miss: a first-year startup's ratios, like the ones computed in the book's own example, are nearly meaningless as health indicators. Ratios are questions, not answers. A deteriorating inventory turn asks "are sales slowing?"; the answer requires looking at the business, not the ratio.

---

## 9. Valuation methods as a coherence check

**How it works, step by step.** The book values the same company four ways and gets four different answers: book value (assets minus liabilities, $1.7M), liquidation value (fire-sale assumptions on inventory and equipment, under $500K), price-earnings multiple ($1.26 earnings per share times a 12x industry multiple, about $3M), and discounted cash flow (declared too assumption-laden to use). Market value does not exist because the company is private.

**Analyst application.** The spread between the methods is the signal. When liquidation value is a fraction of earnings-multiple value, the company's worth lives entirely in its ability to keep operating and growing, which means debt backed by "value" is backed by a story, not by assets. For risk work, always compute the downside valuation alongside the rosy one. If the downside number does not cover the debt, you are underwriting growth, not collateral. The book is honest that discounted cash flow is too complex for its purposes; the sharper takeaway is that any valuation resting on estimated future cash flows is only as good as the revenue recognition and policy choices feeding the estimates.

---

## Popular take vs sharper argument

1. **Popular take: creative accounting is fine and legal; cooking the books is fraud, and they are different things.** Sharper argument: the mechanics are identical. Capitalizing vs expensing, FIFO vs LIFO, lengthening depreciation, lowering reserves, easing revenue recognition: these are the fraud playbook with legal licensing. The difference is intent and disclosure, neither of which appears in the numbers. That is why the book's own strongest fraud signal is not any single policy but a policy *change*: a company switching from conservative to aggressive posture is waving the same flag whether or not a law was broken. Read the policy table in the accounting-policies section as the fraud chapter's table of contents.

2. **Popular take: ratios tell you which company is healthier.** Sharper argument: the book's own industry comparison undermines this. A 1% margin at a grocery chain and a 25% margin at a software company are both "normal"; an inventory turn of 90 at a restaurant and 2 at a manufacturer are both "normal". Ratios only mean something against history, a direct competitor, or an industry benchmark, and the most useful ratio questions in the book are trend questions ("receivable days are lengthening, why?"), not level questions. The example company's own computed ratios, on a single year of a startup's life, are presented straight-faced and are nearly useless as health measures. Treat ratios as a diagnostic checklist, not a scoreboard.

3. **Popular take: profit measures success; a profitable company is a healthy company.** Sharper argument: the worked example refutes this directly. The company earns $251,883 in net income for the year and is cash-flow negative for the year. Fast profitable growth consumes cash (receivables and inventory must be funded before sales are collected), and the cash flow statement is the statement that tells you whether the profit is real in the only sense that matters for survival. For risk analysis, cash from operations is the senior metric; net income is the junior one.

---

## Strongest steelmanned objection

The strongest objection: this whole framework teaches the grammar of a 20th-century manufacturing company and mistakes it for business reality. The measurement principle excludes the assets that matter most in a modern firm (loyal customers, data, brand, human capital are all off the books by rule). Historical cost makes the balance sheet a fiction for asset-light businesses. The cost-vs-expense machinery, depreciation schedules, and inventory turns are manufacturing concepts that translate awkwardly to services, software, and fintech, where the analogous judgments (capitalized development, loan-loss provisions) follow different rules and the book says little about them. And the ratio section computes precise ratios on a single startup year as if they meant something, which teaches false confidence.

Does it hold? In part, yes. No risk analyst should mistake these statements for a complete picture of a company, and the framework's blind spots (intangibles, forward-looking risk, off-balance-sheet exposure) are exactly where modern failures hide. But for the stated purpose, detecting incoherence and manipulation, the objection misses the point: the accrual/matching/policy machinery is domain-independent. A fintech company does not have inventory, but it has provisions, capitalized costs, revenue recognition judgments, and policy changes, and the same discipline applies: bridge profit to cash, watch policy changes, separate recurring from one-time, benchmark ratios against history and peers. The framework is a coherence detector, not a valuation engine, and it is very good at the first job. Read the mechanics as universal; read the ratios and manufacturing examples as one dialect of a larger language.

---

## Practitioner's checklist

1. Bridge net income to operating cash flow yourself: add back depreciation and other non-cash charges, then adjust for receivable, inventory, and payable changes. Is the gap persistent or one-off?
2. Is operating cash flow trailing net income for multiple periods? Which working-capital line is absorbing the difference?
3. Compute days-sales-outstanding and its trend. Are receivables growing faster than revenue?
4. Compare stated payment terms against actual collection days. A 30-day policy with 54-day reality is a collection problem, not a sales success.
5. Compute inventory turns and their trend. Slowing turns with flat or falling sales mean product is piling up.
6. Read the accounting policy footnotes year over year. Any change in inventory method, depreciation life, revenue recognition, or capitalization policy is a red flag until proven innocent.
7. Classify the company's posture: conservative (high reserves, fast depreciation, expense everything) or aggressive (low reserves, slow depreciation, capitalize spending). Discount aggressive profits accordingly.
8. Strip one-time items out of operating income: asset-sale gains, restructuring reversals, "other income". Would the company still be profitable? Would it still clear its covenants?
9. Check gross margin trend vs direct competitors. Margin erosion that peers do not share is a pricing or cost problem, not an industry cycle.
10. Examine depreciation schedules: have useful lives been extended? Compare capital expenditure against depreciation; a company that never replaces what it depreciates is liquidating itself slowly.
11. Look at reserves and allowances (bad debt, warranty, returns). Do they move in the convenient direction when profit is under pressure?
12. Map the debt: current portion of long-term debt against cash on hand, debt-to-equity against industry norms. Is the equity cushion real or inflated by aggressive asset values?
13. Dividends and buybacks: are distributions funded by operating cash flow or by borrowing? A dividend paid while operating cash flow is negative is a warning.
14. Related-party and concentrated-customer sales: who are the big receivables owed by, and what happens if one fails? (The bankrupt-customer write-off is the template.)
15. Finally, ask the coherence question the whole framework points at: does the story the income statement tells match the story the balance sheet and cash flow statement tell? When they disagree, trust the cash.

---

## Weak sections (one line each)

- The "how the statements connect" section is mostly diagrams that do not survive text extraction, so the connections are better learned from the transaction walkthrough than from that section itself.
- The journals-and-ledgers material is pre-digital bookkeeping mechanics with little analytical value for a modern reader.
- The valuation section is thin by its own admission (discounted cash flow is waved away as "too complex"), useful only as a reminder that method choice drives the answer.
- Taxation is simplified to a flat-rate charge; real tax accounting is a separate discipline this book does not teach.
