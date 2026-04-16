# awaithumans

**Your agents already await promises. Now they can await humans.**

The human layer for AI agents — open source, developer-native.

```python
from awaithumans import await_human
from pydantic import BaseModel, Field

class Decision(BaseModel):
    approved: bool = Field(description="Approve this refund?")

result = await await_human(
    task="Approve this refund?",
    payload_schema=RefundPayload,
    payload=RefundPayload(amount=240, customer="cus_123"),
    response_schema=Decision,
    timeout_seconds=900,
)
```

## Install

```bash
pip install awaithumans                  # SDK only
pip install "awaithumans[server]"        # SDK + server + dashboard
```

## Documentation

- [GitHub](https://github.com/awaithumans/awaithumans)
- [Docs](https://awaithumans.dev)

## License

MIT
