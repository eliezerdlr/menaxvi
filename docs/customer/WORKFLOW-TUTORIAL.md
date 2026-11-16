# Tutorial: run the reviewed campaign-message workflow

## Scope

This tutorial covers the only currently validated workflow:

```text
workflow.reviewed-campaign-message@1.0.0
```

The manual adapter creates a deterministic plan and records operator-supplied results. It does not generate or publish a message autonomously.

## 1. Copy the example inputs

```bash
work="$(mktemp -d)"
cp examples/reviewed-campaign-message/inputs.json "$work/inputs.json"
```

Review the brief and evidence before use. Do not insert credentials, private customer data, or unsupported claims.

## 2. Validate workflow readiness

```bash
PYTHONPATH=tooling python3 -m menaxvi workflow validate \
  --root "$(pwd)" \
  --workflow workflow.reviewed-campaign-message@1.0.0 \
  --json "$work/readiness.json"
```

Expected summary:

```text
VALID workflow=workflow.reviewed-campaign-message@1.0.0 nodes=1 tasks=1 gates=1 adapter=manual
```

## 3. Create a deterministic plan

Use a unique, non-secret execution identifier:

```bash
PYTHONPATH=tooling python3 -m menaxvi workflow plan \
  --root "$(pwd)" \
  --workflow workflow.reviewed-campaign-message@1.0.0 \
  --execution-id tutorial-001 \
  --inputs "$work/inputs.json" \
  --output "$work/plan.json"
```

The plan includes the approved task steps, required outputs, review criteria, allowed gate decisions, and a SHA-256 plan digest.

## 4. Perform the work manually

Follow the instructions in `plan.json`:

1. extract factual inputs;
2. draft the campaign message;
3. create the claim ledger;
4. perform the quality review;
5. obtain the required human approval decision.

No content may be treated as approved merely because a plan exists.

## 5. Record results

Copy the example result shape and replace its placeholder values with actual results:

```bash
cp examples/reviewed-campaign-message/results.json "$work/results.json"
```

The `executionId` in the results must match the plan. Then run:

```bash
PYTHONPATH=tooling python3 -m menaxvi workflow record \
  --plan "$work/plan.json" \
  --results "$work/results.json" \
  --output "$work/record.json"
```

A completed record binds the supplied results to the plan digest and adds a deterministic record digest. It is evidence of what the operator supplied; it is not proof that external publication occurred.

## Negative paths

The recorder rejects:

- a changed or tampered plan;
- an execution ID mismatch;
- missing or unexpected task outputs;
- a gate decision outside the approved decision list;
- a passed gate without its required decision evidence.

If the task fails, record the node as `failed` and the approval gate as `not-run`, with clear reasons. Do not mark a failed or unreviewed execution as completed.

## Retry a failed execution

A retry creates a new plan. It does not overwrite the failed record. The workflow's `failurePolicy.maxAttempts` limit is enforced, and the new plan contains lineage to the prior record.

```bash
PYTHONPATH=tooling python3 -m menaxvi workflow retry \
  --plan "$work/plan.json" \
  --record "$work/record.json" \
  --execution-id tutorial-002 \
  --output "$work/retry-plan.json"
```

Use the retry plan as the plan for the new attempt. Preserve both attempts and their evidence.

## Prepare a rollback

MENAXVI cannot infer or reverse external effects. The rollback command creates a digest-bound compensating-action plan and explicitly records that no automatic action occurred.

```bash
PYTHONPATH=tooling python3 -m menaxvi workflow rollback \
  --plan "$work/plan.json" \
  --record "$work/record.json" \
  --reason "Customer withdrew the request" \
  --output "$work/rollback.json"
```

An authorized operator must identify and reverse any external effects, preserve the original evidence, and separately record actions, timestamps, outcomes, and residual risks.
