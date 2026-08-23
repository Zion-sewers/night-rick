# Property-Based Test Generator

**Purpose:** Generate tests that verify invariants hold for all inputs, not just specific examples.

**When to Use:**
- Testing mathematical properties (aspect ratio preservation, bounds clamping)
- Validating business rules (signal score 0.0-5.0, tier always S/A/B/C)
- Finding edge cases automatically

**Philosophy:**
❌ **Example-based**: "Given input [3,1,2], output should be [1,2,3]"
✅ **Property-based**: "For ANY array, sorted output length = input length AND output is sorted"

---

## JavaScript/TypeScript (fast-check)

```bash
# Install fast-check (one-time)
bun add -D fast-check

# Example property test
import fc from 'fast-check';

test('aspect ratio always preserved', () => {
  fc.assert(fc.property(
    fc.record({
      width: fc.integer({ min: 100, max: 2000 }),
      height: fc.integer({ min: 100, max: 2000 }),
      type: fc.constant('IMAGE')
    }),
    (node) => {
      const locked = applyAspectRatioLock(node);
      const originalRatio = node.width / node.height;
      const newRatio = locked.width / locked.height;
      expect(Math.abs(originalRatio - newRatio)).toBeLessThan(0.01);
    }
  ));
});
```

---

## Python (Hypothesis)

```bash
# Install Hypothesis (one-time)
uv pip install hypothesis

# Example property test
from hypothesis import given, strategies as st

@given(
    platform=st.sampled_from(['meta', 'tiktok']),
    signal_score=st.floats(min_value=0.0, max_value=5.0)
)
def test_signal_score_invariant(platform, signal_score):
    """Signal score always 0.0-5.0 for all platforms."""
    record = NormalizedRecord(platform=platform, signal_score=signal_score)
    assert 0.0 <= record.signal_score <= 5.0
```

---

## Common Invariants to Test

**From a design-tool canvas engine:**
- Aspect ratio preservation for images/logos
- Bounds clamping (all nodes within frame ±2px)
- Constraint solving (SCALE constraints never distort)
- Layout coherence (sibling pair delta ≤0.5px)

**From a campaign-scoring domain (10 System Invariants):**
1. Normalized record IDs are stable (never change)
2. Briefs reference a valid parent id
3. Experiments reference a valid brief id
4. Signal score: 0.0-5.0 (NOT 0-1)
5. Tier: S, A, B, or C
6. Confidence: 'high' or 'degraded'
7. Geo: a fixed enum of launch regions (Phase 1)
8. Platform: 'meta' or 'tiktok'
9. Angle: fomo, social-proof, urgency, authority, other
10. SLA deadline: always future when brief created

---

## Tips

**Start Small:**
```javascript
// Bad: Too broad
fc.anything() // Generates nonsense

// Good: Constrained
fc.integer({ min: 0, max: 100 })
```

**Shrinking:**
When property tests fail, fast-check/Hypothesis automatically find the **minimal failing case**.

Example:
```
Initial failure: width=1847, height=523
Shrunk to: width=2, height=1  ← Minimal reproduction!
```

**Official References:**
- [fast-check docs](https://fast-check.dev/)
- [Hypothesis docs](https://hypothesis.readthedocs.io/)
