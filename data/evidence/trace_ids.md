# Langfuse Trace Evidence

Exported 10 traces named `chat_request`.

| # | Trace ID | Correlation ID | Scenario |
|---:|---|---|---|
| 1 | [dcb03b0a4962244dfc0d10bc86bb9fa6](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/dcb03b0a4962244dfc0d10bc86bb9fa6) | eadf1828-f93c-4538-92c4-9bc2d54abee7 | tool_fail |
| 2 | [6d6a7a57460e79733e7e4e03f6a814d0](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/6d6a7a57460e79733e7e4e03f6a814d0) | 71e3b557-de0c-4028-9d00-b20bd3f85f92 | cost_spike |
| 3 | [7bad5794cc7e97ce4b567f1a8a8508b6](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/7bad5794cc7e97ce4b567f1a8a8508b6) | 23580492-d302-422b-9e36-e8db8280f3b0 | rag_slow |
| 4 | [49085286eef57e9f1f60ff8b0b347dc9](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/49085286eef57e9f1f60ff8b0b347dc9) | f3f946e3-dfd5-44e2-af0b-b9e927438704 | baseline |
| 5 | [7e96266c3084d1a64f7d6e19b849d44f](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/7e96266c3084d1a64f7d6e19b849d44f) | b2cdb1a2-bb57-4797-8a29-654715db2213 | baseline |
| 6 | [1250ea80732750e810a6691128144a34](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/1250ea80732750e810a6691128144a34) | 83e1f228-4825-4298-845e-6a1b590c8391 | baseline |
| 7 | [4813099c3df2c83f45e4a95f80a75632](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/4813099c3df2c83f45e4a95f80a75632) | 38c0b432-934f-455f-84ed-5d296316db67 | baseline |
| 8 | [953a80f510e47687c3d57f6f0d4c40e0](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/953a80f510e47687c3d57f6f0d4c40e0) | 910a3c47-d76a-4a4f-943e-ff5aea9c6999 | baseline |
| 9 | [2b96c5cb04bc85c9beafa9a966f68e95](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/2b96c5cb04bc85c9beafa9a966f68e95) | ddc4c761-3d58-4dd2-b02b-4a93eec6347d | baseline |
| 10 | [0ebe4d3335fc976e75cc372514096df1](https://cloud.langfuse.com/project/cmqexw8eb00hqad0coovsa2km/traces/0ebe4d3335fc976e75cc372514096df1) | 59e3f801-d6c6-41ed-a66b-1b6c254d63cb | baseline |

Expected observation tree:

```text
chat_request (SPAN)
  rag.retrieve (RETRIEVER)
  llm.generate (GENERATION)
  metrics.record (SPAN)
```
