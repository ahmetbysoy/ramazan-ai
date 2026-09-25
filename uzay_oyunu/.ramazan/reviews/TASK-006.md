# Review History for TASK-006

## Attempt 1 — 2026-09-25T22:24:54Z

**Status:** `CHANGES_REQUIRED`
**Severity:** `HIGH`

### Summary
Screen wrapping logic contains a severe bug with negative coordinate comparisons, and tests are written in TypeScript/Vitest while the project runner expects Python tests (resulting in 0 tests ran).

### Issues Identified
- **[CORRECTNESS]** `src/entities/asteroid.ts` (line 49): The screen wrapping logic `(newPos.x + asteroid.radius * 2) < 0` is incorrect. Adding `asteroid.radius * 2` when checking if the left side has gone past the screen causes wrapping to trigger prematurely or incorrectly.
  - *Required Fix:* Change the left boundary wrap condition to check `newPos.x + asteroid.radius < 0` wrapping to `canvasWidth + asteroid.radius`, and similarly for the Y axis.
- **[TESTING]** `tests/entities/asteroid.test.ts` (line 1): Unit tests are written using Vitest/TypeScript, but the test runner environment runs pytest (Python), resulting in 0 tests executed during the review cycle.
  - *Required Fix:* Ensure test files match the required language/framework runner of the architecture or configure the test pipeline to execute Vitest properly.


---

## Attempt 2 — 2026-09-25T22:25:19Z

**Status:** `CHANGES_REQUIRED`
**Severity:** `HIGH`

### Summary
The implementation contains critical defects in velocity vector calculation during splitting, architectural violations regarding mutable state (ID counters), and insufficient testing coverage for velocity directional checks.

### Issues Identified
- **[CORRECTNESS]** `src/entities/asteroid.ts` (line 105): The `splitAsteroid` function calculates child velocities using vector components in a way that does not accurately simulate physical splitting conservation of momentum or proper angular divergence. Furthermore, mixing additions and subtractions of cross-components without proper normalization can lead to unpredictable child trajectories or zero-velocity vectors.
  - *Required Fix:* Refactor child velocity calculations to rotate the parent's velocity vector by fixed angles (+/- 45 degrees, for example) to ensure consistent divergence and valid speed.
- **[ARCHITECTURE]** `src/entities/asteroid.ts` (line 20): The module uses a mutable module-level variable (`let nextAsteroidId = 1`) and a reset function. This violates the functional/immutability architectural principle and introduces shared state side-effects across tests or game sessions.
  - *Required Fix:* Remove module-level mutable state and ID counters. Generate unique IDs via a pure mechanism (such as crypto.randomUUID() or passing an ID generator/factory function).
- **[EDGE_CASES]** `src/entities/asteroid.ts` (line 49): In `updateAsteroid`, the screen wrapping logic uses an overly simplistic offset check that can cause stuttering or infinite wrapping loops if the velocity is high or dt is large relative to canvas dimensions.
  - *Required Fix:* Implement robust modulo-based screen wrapping that accounts for radius properly without edge-teleportation artifacts.
- **[TESTING]** `tests/entities/asteroid.test.ts` (line 52): The unit test for `spawnAsteroidAtBoundary` only checks if the spawn position is outside the canvas, but does not verify the acceptance criteria requirement that velocities are 'directed inward' towards the canvas center.
  - *Required Fix:* Add assertions checking that the dot product of the velocity vector and the vector from position to canvas center is positive (indicating movement toward the center).


---

## Attempt 3 — 2026-09-25T22:25:28Z

**Status:** `APPROVED`
**Severity:** `LOW`

### Summary
The asteroid entity and spawning system implementation is clean, modular, immutable, and properly tested. Vector math, screen wrapping via modulo offset ranges, collision checks, and splitting mechanics are correctly implemented.

### Issues Identified
_No issues found. Code meets acceptance criteria._

