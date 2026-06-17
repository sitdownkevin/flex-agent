# Direct Inference Batch Coding

You are analyzing Chinese user reviews about immersive metaverse/VR game experience value.

Directly open-code the batch of reviews below and output a tabular JSON object. Extract only fragments that directly describe experience value, such as service, devices, visuals, sound, interaction, gameplay, price, location, environment, comfort, emotions, recommendation intent, or revisit intent.

Requirements:

1. Each review may have zero or more `items`.
2. Assign each item one concise English `dimension`, plus one higher-level English `category`.
3. `dimension` and `category` should be reusable across reviews; do not mechanically copy the source sentence.
4. `value` must be `1` or `-1`, representing positive or negative experience value.
5. Output JSON only. Do not output Markdown, explanations, or extra text.

Output JSON schema:

```json
{
  "records": [
    {
      "text_id": 1,
      "items": [
        {
          "evidence": "source fragment",
          "dimension": "concise English dimension",
          "category": "higher-level category",
          "value": 1,
          "reason": "one brief rationale"
        }
      ]
    }
  ]
}
```

Input review JSON:

{records_json}
