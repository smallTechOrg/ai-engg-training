"""17.4/1  When is fine-tuning warranted? A checklist, a break-even and the LoRA arithmetic

Fine-tuning trains the model further on your examples, so its weights (the numbers inside it)
change. It is the LAST tool to reach for. This script (no model call, no GPU) shows three things:
  1. the ladder of cheaper options to try first, as a checklist,
  2. a break-even calculation: does a shorter prompt after fine-tuning repay the training cost?
  3. why LoRA and QLoRA are cheap: the number of trainable parameters and the memory,
     computed from the shapes of a 7-billion-parameter model.
All prices and volumes are INVENTED: put your own numbers in the constants at the top.

Run it:   ./run 17.4/1          (Windows: run 17.4/1)
     or:  python modules/17-monitoring-and-fine-tuning/04-fine-tuning/01_when_to_fine_tune.py
"""

from labkit import lesson

# --- invented business numbers for the Larkspur Labs helpdesk -------------------
TICKETS_PER_MONTH = 400_000
PROMPT_TOKENS_TODAY = 900  # long system prompt with 8 few-shot examples
PROMPT_TOKENS_AFTER = 120  # the tuned model has learned the format and tone
REPLY_TOKENS = 60
PRICE_IN_PER_M = 0.50  # dollars per million tokens, hosted base model
PRICE_OUT_PER_M = 1.50
TUNED_PRICE_FACTOR = 1.5  # hosted tuned models often cost more per token
TRAINING_COST = 400.0  # one-off: compute plus the people-time to prepare data
RETRAIN_PER_YEAR = 2  # the base model or your policies change

# --- shapes of a 7B-class model (like Llama-style architectures) ----------------
HIDDEN = 4096
LAYERS = 32
TOTAL_PARAMS = 7_000_000_000
RANK = 8
TARGET_MATRICES_PER_LAYER = 2  # LoRA on the query and value projections


def monthly_cost(prompt_tokens, factor):
    t_in = TICKETS_PER_MONTH * prompt_tokens
    t_out = TICKETS_PER_MONTH * REPLY_TOKENS
    return (t_in * PRICE_IN_PER_M + t_out * PRICE_OUT_PER_M) / 1e6 * factor


@lesson("17.4/1", "When is fine-tuning warranted?")
def main(ctx):
    ctx.step("The ladder: try these before changing weights")
    ladder = [
        ("1. Better prompt", "clear role, rules, output format; cheap, reversible, minutes to try"),
        ("2. Few-shot examples", "show 3-8 good answers in the prompt; costs tokens on every call"),
        ("3. Retrieval (RAG, modules 03-04)", "the model needs FACTS it was never trained on: put them in the prompt"),
        ("4. Tools and structured output (02, 08)", "the model needs ACTIONS or exact formats: give it tools and a schema"),
        ("5. A stronger or different model", "often fixes quality for less effort than training"),
        ("6. Fine-tuning", "the model needs a STYLE, FORMAT or NARROW SKILL you cannot get by prompting, at volume"),
    ]
    for name, why in ladder:
        ctx.console.print(f"{name:42} {why}", markup=False)
    ctx.note("Fine-tuning teaches behaviour (tone, format, a classification habit). It is a poor way to teach facts: they go stale and the model can still make things up. Facts belong in retrieval.")

    ctx.step("Warrant checklist: answer these about the helpdesk assistant")
    checks = [
        ("Prompting and few-shot were tried and measured (module 10 eval set)", True),
        ("The gap is style/format/skill, not missing facts", True),
        ("You have 500+ clean, reviewed examples", False),
        ("Volume is high enough that a shorter prompt saves real money", True),
        ("The task is stable (it will not change every month)", False),
    ]
    for text, answer in checks:
        ctx.console.print(f"[{'x' if answer else ' '}] {text}", markup=False)
    ctx.note("Two boxes are open, so Larkspur Labs is not ready. Collect and review data first (script 2), and wait for the policy to settle.")

    ctx.step("Break-even: does a shorter prompt repay the training?")
    today = monthly_cost(PROMPT_TOKENS_TODAY, 1.0)
    after = monthly_cost(PROMPT_TOKENS_AFTER, TUNED_PRICE_FACTOR)
    saving = today - after
    ctx.console.print(f"today:  {PROMPT_TOKENS_TODAY} prompt tokens x {TICKETS_PER_MONTH} tickets = ${today:,.2f} per month", markup=False)
    ctx.console.print(f"tuned:  {PROMPT_TOKENS_AFTER} prompt tokens, price x{TUNED_PRICE_FACTOR} = ${after:,.2f} per month", markup=False)
    ctx.console.print(f"saving: ${saving:,.2f} per month", markup=False)
    yearly_cost = TRAINING_COST * (1 + RETRAIN_PER_YEAR)
    if saving <= 0:
        ctx.note("No saving: only better quality, not cost, could justify fine-tuning here.")
    else:
        ctx.note(f"Training ${TRAINING_COST:,.0f} now plus {RETRAIN_PER_YEAR} retrains a year = ${yearly_cost:,.0f} in year one; it pays back in {yearly_cost / saving:.1f} months.")
    ctx.note("Set TICKETS_PER_MONTH to 40,000 and rerun: payback takes about eight years, so at low volume cost alone never justifies it. Cost is rarely the best reason. Consistent tone and speed are better ones.")

    ctx.step("Why LoRA is cheap: count the trainable parameters")
    full_matrix = HIDDEN * HIDDEN
    lora_matrix = RANK * (HIDDEN + HIDDEN)  # A is r x k, B is d x r, instead of a d x k update
    adapter = LAYERS * TARGET_MATRICES_PER_LAYER * lora_matrix
    ctx.console.print(f"one {HIDDEN}x{HIDDEN} attention matrix: {full_matrix:,} weights", markup=False)
    ctx.console.print(f"its LoRA update at rank {RANK}: {lora_matrix:,} weights ({lora_matrix / full_matrix:.2%})", markup=False)
    ctx.console.print(f"adapter over {LAYERS} layers x {TARGET_MATRICES_PER_LAYER} matrices: {adapter:,} weights = {adapter / TOTAL_PARAMS:.3%} of the {TOTAL_PARAMS / 1e9:.0f}B model", markup=False)
    ctx.note("LoRA freezes the base weights and learns two thin matrices per target layer (A and B). The update is B x A. Only these are trained and saved: a few megabytes, one per task if you like.")

    ctx.step("Why QLoRA fits on one GPU: memory for the frozen weights")
    gb16 = TOTAL_PARAMS * 2 / 1e9
    gb4 = TOTAL_PARAMS * 0.5 / 1e9
    ctx.console.print(f"base weights at 16-bit: {gb16:.1f} GB   at 4-bit (QLoRA): {gb4:.1f} GB", markup=False)
    ctx.note("QLoRA stores the frozen base in 4-bit and trains the LoRA adapters in higher precision. Activations, optimiser state and context length add more memory, so these are minimums, not a recommendation.")
    ctx.note("Full fine-tuning also needs gradients and optimiser state for all 7B weights: several times the weight memory.")


if __name__ == "__main__":
    main()
