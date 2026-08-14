# Documentation style

How to write docs for this project. Follow these rules directly.

## Voice

Write as someone who has actually run this on their own machine, for the person about to. Confident, concrete, unfussy. Never sell, never pad, never make a stuck reader feel stupid.

## Always

- **Open with what it is, who it's for, and the shortest path to working output.** Nothing above that. No "in this guide we will".
- **Say what it does not do, early.** Non-goals and unsupported cases belong in the doc, not in an issue six months later.
- **Deflate, then explain.** When something looks complicated, say so and reduce it: "The reconciler looks complicated but it boils down to a loop: read what you asked for, read what's running, and if they differ, change the second one."
- **Run every snippet and show its output.** A code block with no output is half a document. Never invent pseudocode.
- **Give real numbers.** Versions, memory, wall-clock, limits, costs. "Indexes 17,000 files in ~90s and 6 GB on an M2 Pro", not "fast" or "a large dataset".
- **Gloss jargon inline at first use**, in parentheses: "`gamma`, the R1 regularization parameter".
- **Name limitations and judgment calls explicitly.** "There is no metric that tells you the right chunk size. Start at 512 tokens and adjust by reading the retrieved passages."
- **Say when a choice was arbitrary.** "We use Postgres because we already ran one. Nothing here depends on it." That tells a maintainer the decision is cheap to revisit.
- **Hedge causes, never facts.** "This usually means the config wasn't found; I haven't reproduced it with a valid path" — not "there may be various factors".
- **Date or version-pin anything about external behaviour.** "As of v2.4."
- **Credit people by name** and link generously.

## Never

"Simply", "just", "easy", "obviously", "please note", "it's important to note". Marketing adjectives (blazing fast, seamless, powerful). Bold for emphasis — use backticks for identifiers and admonitions for warnings. Emoji as decoration. A Limitations section that lists no limitations. Deep heading nesting past h3. Apologetic error messages. `<your-value-here>` without saying where to get it.

## Register by document type

| Type | Person | Shape | Humour |
|---|---|---|---|
| README | `you` | What it is → run it → what it doesn't do → requirements → links | One dry line max |
| Tutorial | `we`/`you` | Prerequisites → linear steps → expected output after each | One aside |
| How-to | imperative | Title is the task. First line is step 1. No preamble. | None |
| Reference | none | Identical field order every entry: name, type, default, behaviour, constraints, example | None |
| Design notes | `we` | Problem → what we chose → what we rejected and why | Allowed |
| Troubleshooting | `you` | See shape below | None |
| Changelog | none | Past tense, one line per change, breaking changes first with migration inline | None |

Humour is at most one dry understatement per document, and never in reference, troubleshooting, error text, or security docs. If a joke would make someone debugging a production issue feel worse, cut it.

## Troubleshooting entry shape

Always include what the cause *isn't* — ruling things out saves the reader the diagnosis you already ran.

> **Symptom:** loss drops but output quality gets worse each epoch.
> **Not the cause:** weights are unchanged by the sampling call; we checked.
> **Cause:** `torch.manual_seed()` inside the loop reseeds the global RNG, so the dataloader replays the same order and the model learns the order.
> **Fix:** `generator=torch.Generator(device='cpu').manual_seed(seed)`

## Error messages

What happened, why, what to do. No apology.

- ❌ `Error: Invalid configuration.`
- ✅ `Invalid config: 'chunk_size' is 4096 but model 'all-MiniLM-L6-v2' accepts at most 512 tokens. Set chunk_size <= 512 or choose a longer-context model.`

## Examples

**README opening**

> ❌ Welcome to Foo! Foo is a powerful, flexible, easy-to-use library that revolutionizes document indexing. Whether you're a beginner or an expert, Foo has something for you.

> ✅ Foo indexes a directory of documents and answers queries against them. It's for people who want retrieval working in an afternoon without running a vector database.
>
> ```
> pip install foo
> foo index ./docs
> foo query "how do I rotate a key"
> ```
>
> Indexing 17,000 markdown files takes about 90 seconds and 6 GB of RAM. Foo does not do reranking, hybrid search, or multi-tenancy — if you need those, use Bar.

**Documenting a parameter**

> ❌ `retry_backoff` (float): The retry backoff. Optional.

> ✅ `retry_backoff` (float, default `0.5`): Base delay in seconds. Delay before attempt *n* is `retry_backoff * 2**n`, capped at `retry_max`. Set to `0` to retry immediately, usually only sensible in tests.

**A known problem**

> ❌ Note: Some users may occasionally experience issues with large files. We're working on improving this.

> ✅ Files above about 200 MB fail with `MemoryError` because the parser reads the whole file before chunking. No workaround other than splitting the file. Tracked in #412.

## Before you finish

- [ ] First three lines: what it is, who it's for, how to run it
- [ ] Non-goals and limitations stated, and real
- [ ] Every snippet run; output shown
- [ ] Every identifier in backticks; every limit a number
- [ ] Register matches the document type
- [ ] Troubleshooting entries say what the cause isn't
- [ ] No banned words; no bold for emphasis
- [ ] External behaviour dated or version-pinned
- [ ] Error messages give an action, not an apology
- [ ] Breaking changes at the top with migration inline
